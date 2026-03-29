import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import PySpice.Logging.Logging as Logging
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import u_V, u_um

# ============================================================
# 1. Setup & Technology Definitions
# ============================================================
# Absolute path to your PTM model files. 
# Create a folder named 'models' in your project directory and place your .pm files there
MODEL_DIR = Path("./models")
# TECHS: Dictionary defining process-specific constraints.
# L_nm: Minimum gate length.
# VDD: Nominal supply voltage (scales down for smaller nodes to protect gate oxide).
TECHS = {
    "22nm":  {"l_nm": 22,  "vdd": 0.8, "model": MODEL_DIR / "22nm_bulk.pm"},
    "32nm":  {"l_nm": 32,  "vdd": 0.9, "model": MODEL_DIR / "32nm_bulk.pm"},
    "45nm":  {"l_nm": 45,  "vdd": 1.0, "model": MODEL_DIR / "45nm_bulk.pm"},
    "65nm":  {"l_nm": 65,  "vdd": 1.0, "model": MODEL_DIR / "65nm_bulk.pm"},
    "90nm":  {"l_nm": 90,  "vdd": 1.2, "model": MODEL_DIR / "90nm_bulk.pm"},
    "130nm": {"l_nm": 130, "vdd": 1.2, "model": MODEL_DIR / "130nm_bulk.pm"},
}

W_OVER_L = 80.0    # Fixed aspect ratio to normalize current density comparisons.
TEMP_C = 27        # Standard room temperature for characterization.
VGS_STEP = 0.0005  # 0.5mV steps: high resolution required for accurate gm/gds derivatives.

def extract_nmos_parasitics(model_path: Path):
    """
    Layout-Aware Parsing: Standard DC sweeps often miss overlap parasitics.
    This function scans the .pm file for CGDO and CGDL (Gate-Drain overlaps).
    """
    text = model_path.read_text(errors="ignore")
    # Isolate NMOS section to avoid picking up PMOS parameters.
    nmos_text = re.split(r"(?im)^\s*\.model\s+pmos\b", text, maxsplit=1)[0]
    try:
        cgdo = float(re.search(r"cgdo\s*=\s*([0-9.eE+-]+)", nmos_text, re.I).group(1))
        cgdl = float(re.search(r"cgdl\s*=\s*([0-9.eE+-]+)", nmos_text, re.I).group(1))
        return cgdo + cgdl
    except (AttributeError, ValueError):
        return 0.0

def safe_div(num, den, eps=1e-30):
    """Prevents simulation crashes due to 'Division by Zero' at Vgs=0."""
    return num / np.maximum(np.abs(den), eps)

logger = Logging.setup_logging()
tech_data = {}

# ============================================================
# 2. Simulation Loop (The Automated Testbench)
# ============================================================
for tech_name, spec in TECHS.items():
    model_path = spec["model"]
    if not model_path.exists():
        print(f"Skipping {tech_name}: model file not found.")
        continue

    try:
        # Physical Dimension Scaling
        l_um = spec["l_nm"] * 1e-3
        w_um = W_OVER_L * l_um
        vdd = spec["vdd"]
        vds = 0.5 * vdd # Biasing VDS at VDD/2 ensures Saturation Region characterization.
        
        p_sum = extract_nmos_parasitics(model_path)
        
        # Netlist Generation
        circuit = Circuit(f"NMOS_{tech_name}")
        circuit.include(str(model_path))
        
        # Define Bias Sources
        Vgate = circuit.V("gate", "gatenode", circuit.gnd, 0 @ u_V)
        Vdrain = circuit.V("drain", "vdd_node", circuit.gnd, vds @ u_V)
        
        # Instantiate MOSFET (M1)
        circuit.MOSFET(1, "vdd_node", "gatenode", circuit.gnd, circuit.gnd, 
                       model="nmos", w=w_um @ u_um, l=l_um @ u_um)
        
        simulator = circuit.simulator(temperature=TEMP_C)
        # Specific save commands to extract internal SPICE operating point parameters.
        simulator.save(["all", "@m1[gm]", "@m1[gds]", "@m1[cgg]", "@m1[cgd]", "@m1[id]"])
        
        # Execute the DC Sweep
        analysis = simulator.dc(Vgate=slice(0, vdd, VGS_STEP))
        
        # Convert raw SPICE output to Numpy arrays for processing.
        ip = analysis.internal_parameters
        Id = np.abs(np.array(ip["@m1[id]"]))
        gm = np.abs(np.array(ip["@m1[gm]"]))
        gds = np.abs(np.array(ip["@m1[gds]"]))
        cgg = np.abs(np.array(ip["@m1[cgg]"]))
        cgd_intrinsic = np.abs(np.array(ip["@m1[cgd]"]))

        # Line 83: The Miller Correction. 
        # Adding overlap/fringing parasitics (p_sum) to the intrinsic Cgd.
        cgd_total = cgd_intrinsic + (p_sum * w_um * 1e-6)
        
        # Generate the Design Lookup Table (DataFrame)
        df = pd.DataFrame({
            "Vgs": np.array(analysis.sweep),
            "gm_id": safe_div(gm, Id),
            "gain": safe_div(gm, gds),
            "fT": safe_div(gm, (2 * np.pi * cgg)),
            "id_w": (Id / w_um) * 1e6, # Scale to uA/um for easier layout calculation.
            "cgd": cgd_total,
            "cgd_id": safe_div(cgd_total, Id)
        }).dropna()

        # Save to CSV: These files are your 'Golden Data' for sizing.
        csv_filename = f"nmos_{tech_name}_results.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Successfully saved results for {tech_name} to {csv_filename}")

        # Filter gm/id range: 3 to 35 covers Weak, Moderate, and Strong Inversion.
        df_plot = df[(df["gm_id"] > 3) & (df["gm_id"] < 35)]
        tech_data[tech_name] = df_plot
        
        print(f"Finished simulating {tech_name}")

    except Exception as e:
        print(f"Error simulating {tech_name}: {e}")

# ============================================================
# 3. 8-Panel Comparison Dashboard (The Design Visualization)
# ============================================================
if tech_data:
    fig, axs = plt.subplots(2, 4, figsize=(22, 11))
    axs = axs.flatten()

    for tech_name, df in tech_data.items():
        # Sort by gm_id to ensure clean line plotting for X-axis comparisons.
        df_s = df.sort_values("gm_id")

        # Plot 1: Efficiency vs. Gate Drive
        axs[0].plot(df["Vgs"], df["gm_id"], lw=2, label=tech_name)
        axs[0].set_title(r"$g_m/I_D$ vs $V_{gs}$")
        
        # Plot 2: Intrinsic Gain (Design limit for a single stage)
        axs[1].plot(df_s["gm_id"], df_s["gain"], lw=2, label=tech_name)
        axs[1].set_title(r"Intrinsic Gain ($g_m/g_{ds}$)")

        # Plot 3: Speed (fT) - Crucial for LNA and switching circuits.
        axs[2].plot(df_s["gm_id"], df_s["fT"]/1e9, lw=2, label=tech_name)
        axs[2].set_yscale("log")
        axs[2].set_title(r"$f_T$ [GHz] (Log Scale)")

        # Plot 4: Figure of Merit (Trade-off between Speed and Efficiency)
        axs[3].plot(df_s["gm_id"], (df_s["gm_id"]*df_s["fT"])/1e9, lw=2, label=tech_name)
        axs[3].set_title(r"FOM: $(g_m/I_D) \cdot f_T$")

        # Plot 5: Bias Mapping (Translate design choice to Vgs)
        axs[4].plot(df_s["gm_id"], df_s["Vgs"], lw=2, label=tech_name)
        axs[4].set_title(r"$V_{gs}$ vs $g_m/I_D$")

        # Plot 6: Current Density (The layout sizing tool)
        # Use this to find W = Id_target / (Id/W_plot)
        axs[5].plot(df_s["gm_id"], df_s["id_w"], lw=2, label=tech_name)
        axs[5].set_yscale("log")
        axs[5].set_title(r"Current Density $I_d/W$ [$\mu$A/$\mu$m]")

        # Plot 7 & 8: Parasitic Analysis (Stability and Miller Effect)
        axs[6].plot(df_s["gm_id"], df_s["cgd"]*1e18, lw=2, label=tech_name)
        axs[6].set_title(r"Corrected $C_{gd}$ [aF]")

        axs[7].plot(df_s["gm_id"], df_s["cgd_id"], lw=2, label=tech_name)
        axs[7].set_yscale("log")
        axs[7].set_title(r"Corrected $C_{gd}/I_d$ [F/A]")

    # Formatting the dashboard
    for i, ax in enumerate(axs):
        ax.grid(True, which="both", ls="--", alpha=0.5)
        ax.legend(fontsize=8)
        if i != 0: ax.set_xlabel(r"$g_m/I_D$ [V$^{-1}$]")

    plt.tight_layout()
    plt.show()
else:
    print("No data simulated. Please check MODEL_DIR paths.")
