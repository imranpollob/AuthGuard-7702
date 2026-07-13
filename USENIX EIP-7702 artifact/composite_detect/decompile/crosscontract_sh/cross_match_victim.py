import pandas as pd

# Final Victim Matching and Ethical Considerations.
# After identifying attacker contracts, we further reuse our cross_match.py 
# script to match their potential victims based on transaction interactions. The final
#  matched results are stored in result.xlsx. For ethical considerations, we 
# have intentionally hidden the addresses of victim contracts to prevent potential misuse. 
# Researchers can manually verify the results by comparing result.xlsx and mid_matched_results.xlsx.

matched_df = pd.read_excel("matched_results.xlsx")
delegated_df = pd.read_excel("sa_contract.xlsx") 

matched_df["target_address"] = matched_df["target_address"].str.lower()
delegated_df["delegated_address"] = delegated_df["delegated_address"].str.lower()

filtered_df = matched_df[matched_df["target_address"].isin(delegated_df["delegated_address"])]

filtered_df.to_excel("matched_in_delegated.xlsx", index=False)


