import jsonlines
import json
import pandas as pd
# 步骤 1: 读取 flashloan.jsonl，提取 address -> set of func signatures
flashloan_funcs = {}

with jsonlines.open("flashloan.jsonl", "r") as reader:
    for item in reader:
        addr = item["address"].lower()
        sigs = set()
        for r in item.get("result", []):
            func_sig = r[4]
            sigs.add(func_sig)
        if sigs:
            flashloan_funcs[addr] = sigs

print(f"✅ 读取 flashloan.jsonl 完成，共 {len(flashloan_funcs)} 个地址含函数签名: {flashloan_funcs}")

# === 加载 related_contracts.xlsx ===
related_df = pd.read_excel("related_contracts.xlsx")
related_df['target_address'] = related_df['target_address'].str.lower()
related_df['related_contracts'] = related_df['related_contracts'].apply(eval)  # 转回 list


# 存储匹配结果
matched_results = []

# === 遍历 flashloan_funcs 中的地址 ===
for addr, target_sigs in flashloan_funcs.items():
    # 1. 查找相关合约地址（related contracts）
    row = related_df[related_df['target_address'] == addr]
    if row.empty:
        continue
    related_contracts = row.iloc[0]['related_contracts']  # list of addresses
    
    related_contracts_set = set(related_contracts)  # 加速查找
    
    # 2. 遍历 funcsig.jsonl 中的数据
    with jsonlines.open("funcsig.jsonl", "r") as reader:
        for item in reader:
            contract_addr = item["address"].lower()
            if contract_addr not in related_contracts_set:
                continue
            
            # 3. 提取 result[i][1] 并匹配
            result = item.get("result", [])
            selectors = {r[1] for r in result if len(r) >= 2}
            matched_sigs = selectors & target_sigs  # 交集

            if matched_sigs:
                matched_results.append({
                    "target_address": addr,
                    "related_contract": contract_addr,
                    "matched_selectors": list(matched_sigs),
                    "row": item
                })

print(f"✅ 匹配完成，共 {len(matched_results)} 条结果")

# === 保存结果到 DataFrame 并导出 ===
matched_df = pd.DataFrame(matched_results)
matched_df.to_excel("matched_results.xlsx", index=False)
print("✅ 结果已保存至 matched_results.xlsx")