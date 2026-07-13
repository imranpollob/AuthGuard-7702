import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Infura Project ID placeholder (use environment variable or config file in real use)
INFURA_PROJECT_ID = "YOUR_INFURA_PROJECT_ID"

RPC_ENDPOINTS = {
    "ethereum": f"https://mainnet.infura.io/v3/{INFURA_PROJECT_ID}",
    "polygon": f"https://polygon-mainnet.infura.io/v3/{INFURA_PROJECT_ID}",
    "optimism": f"https://optimism-mainnet.infura.io/v3/{INFURA_PROJECT_ID}",
    "arbitrum": f"https://arbitrum-mainnet.infura.io/v3/{INFURA_PROJECT_ID}",
    "bnb": "https://bsc-dataseed.binance.org/",
    "base": "https://mainnet.base.org",
    "gnosis": "https://rpc.gnosischain.com"
}

def get_code_task(index, chain, address):
    url = RPC_ENDPOINTS.get(chain.lower())
    if not url:
        return index, "unsupported_chain"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getCode",
        "params": [address, "latest"],
        "id": 1
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        bytecode = res.json().get("result", "null_result")
        return index, bytecode
    except Exception as e:
        return index, f"error: {str(e)}"

input_file = "suspected_txs.csv"
df = pd.read_csv(input_file)
df.columns = [col.lower() for col in df.columns]

required_cols = {"chain", "ca_address"}
if not required_cols.issubset(df.columns):
    raise ValueError("Missing required columns: 'chain' and 'ca_address'")

df['bytecode'] = None

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = []
    for idx, row in df.iterrows():
        chain = row['chain']
        address = row['ca_address']
        futures.append(executor.submit(get_code_task, idx, chain, address))

    for f in tqdm(as_completed(futures), total=len(futures), desc="Fetching bytecode"):
        idx, bytecode = f.result()
        df.at[idx, 'bytecode'] = bytecode
        row = df.loc[idx]
        preview = bytecode[:20] if bytecode else 'None'
        print(f"{row['chain'].ljust(10)} | {row['ca_address']} | {preview}...")

output_file = "sus_contracts_with_bytecode.xlsx"
df.to_excel(output_file, index=False)
print(f"\nBytecode fetching completed. Results saved to: {output_file}")
