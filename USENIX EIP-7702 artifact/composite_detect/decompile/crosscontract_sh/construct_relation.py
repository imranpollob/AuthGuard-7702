import pandas as pd


df = pd.read_excel("contracts_with_bytecode.xlsx") 


result = []
for deployer, group in df.groupby('from'):
    ca_list = group['ca_address'].tolist()
    for ca in ca_list:
        related = [c for c in ca_list if c != ca]
        result.append({
            'target_address': ca,
            'deployer': deployer,
            'related_contracts': related
        })


out_df = pd.DataFrame(result)


out_df.to_excel("related_contracts.xlsx", index=False)
