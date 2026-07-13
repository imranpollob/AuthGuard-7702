import os

import pandas as pd

# Path to save output
output_dir = './output_ca'
input_file = "./contracts_with_bytecode.xlsx"
df = pd.read_excel(input_file)
# Iterate over each row in the dataframe
for _, row in df.iterrows():
    chain = row['chain']
    delegated_address = row['ca_address']
    bytecode = row['bytecode']

    # Construct the directory path for each chain
    chain_dir = os.path.join(output_dir, chain)
    
    # Create the directory for the chain if it doesn't exist
    os.makedirs(chain_dir, exist_ok=True)

    # File name based on delegated_address
    file_name = f"{delegated_address.lower()}.hex"
    file_path = os.path.join(chain_dir, file_name)
    
    # Write the bytecode to the file
    with open(file_path, 'w') as f:
        f.write(bytecode)
