# 如何把這個專案放上 GitHub

> 這份檔案是給你（Watson）的上架指引。上架後可以從 repo 刪掉，或留著當開發筆記。

## 前置：確認 .gitignore 有保護你的隱私

上架前**務必確認**以下檔案不會被 commit（已在 `.gitignore` 設定）：

- `config.yaml`（你的個人追蹤清單）← 只有 `config.example.yaml` 會上去
- 任何 `*.xlsx`（除了 `examples/` 下的展示檔）← 你的個人估值報告
- `.env` / `*.key`（API key）

驗證方法：

```bash
git status
# 確認列出來的檔案裡沒有你的個人資料
```

## 步驟一：本機初始化 Git

```bash
cd stock-scenario-valuation
git init
git add .
git status          # ← 再次確認沒有個人檔案被加進去
git commit -m "Initial commit: stage 1 sector-based valuation"
```

## 步驟二：在 GitHub 建立 repo

1. 登入 GitHub → New repository
2. Repository name: `stock-scenario-valuation`
3. Description: `三情境 (Bear/Base/Bull) 美股估值工具 — 輸入代號自動產生估值報告`
4. **Public**（你決定當作者公開）
5. 不要勾「Add README」（本機已有）
6. Create repository

## 步驟三：推上去

```bash
git remote add origin https://github.com/<你的帳號>/stock-scenario-valuation.git
git branch -M main
git push -u origin main
```

## 步驟四：上架後的優化（選用）

- [ ] README 裡的 `<your-username>` 換成你的實際 GitHub 帳號
- [ ] 加 GitHub Topics: `python`, `finance`, `valuation`, `stock-analysis`, `yfinance`
- [ ] 加一張範例輸出截圖到 README（用 examples/ 的 xlsx 開啟截圖）
- [ ] 在個人 LinkedIn / 履歷連結這個 repo（你決定當作者，這是個人品牌資產）

## 注意事項

1. **第一次 push 前一定要 `git status` 確認沒有個人資料**
2. examples/ 裡的 NVDA xlsx 是用範例資料產生的展示檔，可以公開
3. 之後你自己用工具產生的估值（如你真實的投資組合）會被 .gitignore 擋住，不會誤上傳
4. 如果想保持私密，步驟二改選 **Private** 即可（之後隨時可改公開）
