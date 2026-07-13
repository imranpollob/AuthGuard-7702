import pandas as pd

matched_df = pd.read_excel("matched_results.xlsx")
delegated_df = pd.read_excel("sa_contract.xlsx") 

matched_df["target_address"] = matched_df["target_address"].str.lower()
delegated_df["delegated_address"] = delegated_df["delegated_address"].str.lower()

filtered_df = matched_df[matched_df["target_address"].isin(delegated_df["delegated_address"])]

filtered_df.to_excel("matched_in_delegated.xlsx", index=False)
