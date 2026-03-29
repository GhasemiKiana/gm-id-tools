from gm_id_lookup import lookup_gm_id, CSV_PATH_DEFAULT
import pandas as pd

# ==============================
# Choose your gm/Id here
# ==============================
target_gm_id = 10

# Run lookup
result = lookup_gm_id(target_gm_id, csv_path=CSV_PATH_DEFAULT)

print("\n=== gm/Id Lookup Result ===")
print("Requested gm/Id:", target_gm_id)

if result["type"] == "exact":
    print("\nExact match found:")
    print(result["rows"])
else:
    if result["warning"]:
        print("WARNING:", result["warning"])

    nearest = result["nearest_row"]
    interp = result["interpolated"]

    print("\nNearest measured gm/Id:", nearest["gm_id"])
    print("Nearest Vgs:", nearest.get("Vgs"))

    print("\nInterpolated values:")
    for k, v in interp.items():
        print(f"{k:12s} : {v:.6g}")

    # Optional: save interpolated result
    df_out = pd.DataFrame([interp])
    df_out["gm_id_target"] = target_gm_id
    df_out.to_csv("interpolated_result.csv", index=False)
    print("\nSaved interpolated_result.csv")