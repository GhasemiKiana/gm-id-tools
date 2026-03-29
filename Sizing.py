from gm_id_lookup import lookup_gm_id, CSV_PATH_DEFAULT
import pandas as pd

# ==============================
# 1. Inputs: Choose your design point
# ==============================
target_gm_id = 10     # Transconductance efficiency
target_id_ua = 200.0  # Desired total current in micro-amps (uA)

# ==============================
# 2. Run lookup & Interpolation
# ==============================
result = lookup_gm_id(target_gm_id, csv_path=CSV_PATH_DEFAULT)

print("\n=== gm/Id Design Result ===")
print(f"Requested gm/Id: {target_gm_id}")

if result["type"] == "exact":
    interp = result["rows"].iloc[0].to_dict()
else:
    if result["warning"]:
        print("WARNING:", result["warning"])
    interp = result["interpolated"]

# ==============================
# 3. Width (W) Measurement
# ==============================
# Formula: W = Target_Current / Current_Density
id_w_density = interp.get("id_w", 0)

if id_w_density > 0:
    w_needed = target_id_ua / id_w_density
    print(f"Current Density: {id_w_density:.4f} uA/um")
    print(f"Target Current : {target_id_ua} uA")
    print(f"---> Required Width (W): {w_needed:.6f} um")
    
    # Add to dictionary for CSV saving
    interp["target_current_uA"] = target_id_ua
    interp["W_um"] = w_needed
else:
    print("Error: Could not find 'id_w' in the characterization data.")

# ==============================
# 4. Save result
# ==============================
df_out = pd.DataFrame([interp])
df_out["gm_id_target"] = target_gm_id
df_out.to_csv("interpolated_result.csv", index=False)
print("\nSaved updated results to: interpolated_result.csv")