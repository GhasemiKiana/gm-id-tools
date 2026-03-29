import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Optional

def _find_col(cols, candidates):
    """Helper to find a column name from a list of candidates."""
    for cand in candidates:
        for c in cols:
            if cand.lower() == c.lower():
                return c
    return None

def load_and_prepare(path):
    df = pd.read_csv(path)
    cols = df.columns.tolist()
    
    # 1. Standardize gm/Id
    gm_id_col = _find_col(cols, ['gm_id', 'gm/id'])
    if not gm_id_col:
        gm_col = _find_col(cols, ['gm', 'g_m'])
        id_col = _find_col(cols, ['id', 'i_d'])
        df['gm_id'] = df[gm_col] / df[id_col]
    else:
        df['gm_id'] = df[gm_id_col]

    # 2. Standardize Current Density (Id/W)
    id_w_col = _find_col(cols, ['id_w', 'id_per_um', 'id/w', 'id_dens'])
    if id_w_col:
        df['Id_per_um'] = df[id_w_col]
    else:
        # Fallback: if we only have absolute Id, just use it (or assume W=1um)
        id_col = _find_col(cols, ['id', 'i_d'])
        df['Id_per_um'] = df[id_col]

    # 3. Standardize Cgd/Id
    cgd_id_col = _find_col(cols, ['cgd_id', 'cgd/id'])
    if not cgd_id_col:
        cgd_col = _find_col(cols, ['cgd', 'c_gd'])
        id_col = _find_col(cols, ['id', 'i_d'])
        df['cgd_id'] = df[cgd_col] / df[id_col]
    else:
        df['cgd_id'] = df[cgd_id_col]

    return df

def plot_all(csv_path: str, save_path: Optional[str] = None):
    df = load_and_prepare(csv_path)
    
    # Setup 2x3 Grid
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    # Sort for smooth lines
    df_g = df.sort_values(by='gm_id')
    x = df_g['gm_id']

    # 1. Mapping: gm/Id vs Vgs
    df_v = df.sort_values(by='Vgs')
    axes[0].plot(df_v['Vgs'], df_v['gm_id'], color='black', linewidth=2)
    axes[0].set_xlabel("$V_{gs}$ [V]")
    axes[0].set_ylabel("$g_m/I_d$ [V$^{-1}$]")
    axes[0].set_title("$g_m/I_d$ vs $V_{gs}$")

    # 2. Gain
    axes[1].plot(x, df_g['gain'], color='tab:orange')
    axes[1].set_ylabel("Gain ($g_m/g_{ds}$)")
    axes[1].set_title("Gain vs $g_m/I_d$")

    # 3. fT
    axes[2].plot(x, df_g['fT'] / 1e9, color='tab:purple')
    axes[2].set_ylabel("$f_T$ [GHz]")
    axes[2].set_title("$f_T$ vs $g_m/I_d$")

    # 4. FOM (Speed-Power) - Fixed the \c error here using r""
    axes[3].plot(x, (x * df_g['fT']) / 1e9, color='tab:green')
    axes[3].set_ylabel(r"$(g_m/I_d) \cdot f_T$ [GHz/V]")
    axes[3].set_title("FOM vs $g_m/I_d$")

    # 5. Current Density (Log Scale)
    axes[4].plot(x, df_g['Id_per_um'], color='tab:red')
    axes[4].set_yscale('log')
    axes[4].set_ylabel(r"$I_d/W$ [A/$\mu$m]")
    axes[4].set_title("Current Density vs $g_m/I_d$")

    # 6. Cgd/Id (Log Scale) - The "weird" parasitic curve
    axes[5].plot(x, df_g['cgd_id'], color='tab:blue')
    axes[5].set_yscale('log')
    axes[5].set_ylabel(r"$C_{gd}/I_d$ [F/A]")
    axes[5].set_title(r"$C_{gd}/I_d$ vs $g_m/I_d$")

    for ax in axes:
        ax.grid(True, which="both", linestyle="--", alpha=0.5)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    plt.show()

if __name__ == "__main__":
    # Update this filename to match the tech you want to plot
    plot_all('nmos_22nm_results.csv', save_path='tech_comparison.png')