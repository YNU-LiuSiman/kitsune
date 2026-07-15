# Kitsune 剩余实验执行规范

> 本文件是本次剩余实验任务的唯一执行规范。若此前聊天内容与本文件冲突，以本文件为准。

## 1. 项目目标

完成 Kitsune 论文复现实验剩余部分，重点包括：

1. 修复并稳定现有实验框架；
2. 完成 UCI Kitsune 九类攻击中的剩余八类实验；
3. 对每类数据依次完成：完整预检、1000 行 smoke、10000 行 smoke、full run；
4. 计算无需固定阈值的评估指标；
5. 将状态、代码、结果摘要和恢复信息同步到 GitHub；
6. 不修改官方 Kitsune 核心源码。

## 2. 当前项目状态

### 2.1 仓库与分支

- 仓库：`YNU-LiuSiman/kitsune`
- 当前实验分支：`exp/overnight-20260712`
- 当前 Draft PR：`#4`
- 结果根目录：`results/overnight-20260712/`
- 不允许直接修改 `main`
- 不允许合并 PR
- 不允许 force push 或重写历史

### 2.2 两条实验轨道

#### Track A：PCAP 路径

```text
Mirai PCAP
→ FeatureExtractor / AfterImage
→ 100 维特征
→ KitNET
→ RMSE
```

已完成：

- 总包数：764,137
- 特征维度：100
- 自编码器数量：16
- Grace 行数：55,001
- 执行期 RMSE 数：709,136
- 未发现 NaN/Inf
- 未修改官方源码

#### Track B：UCI 预提取特征路径

```text
UCI CSV 特征
→ 去除确认后的索引列
→ 115 维特征
→ KitNET(n=115)
→ RMSE
```

重要结论：

- UCI 特征直接输入 `KitNET(n=actual_feature_dim, ...)`
- 不裁剪、不填充、不强行转成 100 维
- Python PCAP 轨道与 UCI 115 维轨道是两条独立复现路径

### 2.3 已完成的 UCI 实验

Mirai UCI 已完成：

- 总行数：764,137
- 原始列数：116
- 第 1 列为 0 起始索引
- 去索引后为 115 维
- 特征与标签严格对齐
- 前 55,001 行无攻击标签
- 执行期 RMSE 数：709,136
- 良性样本：66,620
- 攻击样本：642,516

### 2.4 待完成数据集

UCI 共九类，Mirai 已完成，剩余八类：

1. OS Scan
2. Fuzzing
3. SSL Renegotiation
4. ARP MitM
5. SYN DoS
6. Active Wiretap
7. SSDP Flood
8. Video Injection

其中：

- OS Scan 已解压并完成过预检，但之前 smoke/full 状态混用，现有结果不可直接认定为 full 完成；
- Fuzzing 曾因标签值带引号（如 `"1"`）读取失败，解析代码已修复，但必须重新回归验证；
- 其余六类待依次处理。

## 3. 固定实验参数

以下参数不得自动调整：

```text
FMgrace = 5000
ADgrace = 50000
grace_rows = 55001
maxAE = 10
learning_rate = 0.1
hidden_ratio = 0.75
```

Grace 行定义：

- Feature Mapping：内部索引 0..5000，共 5001 行
- Autoencoder Training：5001..55000，共 50000 行
- 首个执行期样本索引：55001
- 因此总 Grace 行数为 55,001

## 4. 强制目录结构

每个 UCI 攻击数据集必须使用独立目录：

```text
results/overnight-20260712/uci/<attack>/
├── smoke-1000/
├── smoke-10000/
└── full/
```

不得让 smoke 与 full 共用同一个结果目录或同一个 `status.json`。

## 5. 每次运行必须保存的产物

每个运行目录必须独立保存：

```text
manifest.json
config.json
precheck.json
status.json
metrics.json
source_hashes.json
raw/rmse.csv
raw/rmse_with_labels.csv
raw/sanitized_run_log.txt
```

规则：

- smoke 阶段允许 `rmse.csv` 仅有表头；
- full 阶段必须保存执行期 RMSE；
- 所有路径、日志和文档中不得出现本地个人姓名或绝对用户目录；
- 使用 `<GIT_ROOT>`、`<PROJECT_ROOT>`、`<SOURCE_ROOT>`、`<USER_HOME>` 等占位符脱敏。

## 6. 状态语义

允许状态：

- `smoke_passed`：仅用于 1000/10000 行 smoke；
- `completed`：仅用于 full run 成功；
- `failed`：代码或运行错误；
- `blocked`：数据、格式、空间等外部阻塞；
- `interrupted`：进程中断，可恢复。

禁止：

- smoke 标记为 `completed`；
- 用 `0` 伪装不可计算指标；
- 删除 `status.json` 强制重跑正式结果；
- 覆盖已有成功 full 结果。

## 7. 工程修复要求

执行实验前必须完成并测试：

1. smoke/full 独立目录；
2. `--no-overwrite` 只判断当前单次运行目录；
3. worktree 中 Git SHA 正确获取：使用 `git rev-parse`，不得仅依赖 `.git` 是否为目录；
4. CSV 表头兼容；
5. 0 起始和 1 起始索引列识别；
6. 不误删真实特征列；
7. 一列标签兼容；
8. 两列“索引+标签”兼容；
9. 带引号标签值兼容；
10. 标签最终一维化；
11. 特征与标签严格按行对齐；
12. execution RMSE 与 execution labels 长度一致；
13. 空 RMSE 文件正确生成；
14. `smoke_passed/completed/failed/blocked/interrupted` 状态语义正确；
15. full 成功结果不得被 smoke 覆盖；
16. 日志、配置、哈希、恢复命令必须可追溯。

## 8. 自动化测试要求

至少添加并通过以下测试：

1. 115 维合成特征；
2. 1000 行 smoke；
3. 10000 行 smoke；
4. 独立标签文件；
5. 0 起始索引；
6. 1 起始索引；
7. 无索引；
8. 一列标签；
9. 两列索引+标签；
10. 带引号标签；
11. 无 NaN/Inf；
12. 特征/标签行数一致；
13. smoke `execution_rows=0`；
14. smoke 指标为 `not_applicable` 或 `null + reason`；
15. full execution RMSE 与标签切片等长；
16. `--no-overwrite` 不会误跳过其他数据集或 full。

## 9. 全量预检规范

每个数据集 full 前必须进行完整预检。

### 9.1 读取方式

- 必须分块流式扫描完整特征和标签文件；
- 不允许一次性将数 GB CSV 全部载入内存；
- smoke 可读取前 1000/10000 行，但 full 预检必须扫描全量。

### 9.2 必检项目

每类数据必须记录：

- 特征文件路径；
- 标签文件路径；
- 是否存在表头；
- 原始特征行数；
- 原始列数；
- 索引列检测结果；
- 去索引后的实际特征维度；
- 标签行数；
- 标签列结构；
- 标签唯一值；
- 良性/攻击样本数；
- NaN 数量；
- Inf 数量；
- 特征与标签是否严格对齐；
- 前 55,001 行攻击样本数；
- 数据文件大小；
- SHA-256；
- 预检耗时。

### 9.3 阻塞条件

出现以下任一情况，不得启动 full：

- 特征/标签行数不一致；
- 特征维度无法确认；
- 索引列判断不可靠；
- 标签格式无法可靠解析；
- NaN/Inf 未处理且会影响模型；
- 前 55,001 行存在攻击标签；
- 文件损坏；
- 磁盘空间不足；
- 可能覆盖成功结果。

此时应标记为 `blocked` 或 `failed`，记录原因和恢复命令。

## 10. Smoke Test 规范

### 10.1 smoke-1000

目的仅为验证：

- 文件读取；
- 表头处理；
- 索引列处理；
- 标签解析；
- 特征维度；
- KitNET 初始化；
- Feature Mapper 训练路径；
- 结果落盘；
- 状态写入；
- 日志和哈希生成。

### 10.2 smoke-10000

目的与 1000 行相同，只是提高流程覆盖度。

### 10.3 必须满足

因为 1000 和 10000 都小于 55,001：

```text
execution_rows = 0
```

因此：

- 不计算 ROC-AUC；
- 不计算 PR-AUC；
- 不计算良性/攻击执行期 RMSE；
- 不报告检测能力；
- 指标写 `null` 或 `not_applicable`，并附原因；
- 状态写 `smoke_passed`。

## 11. Full Run 规范

仅当完整预检与两级 smoke 均通过后，才允许 full。

规则：

- 每次只运行一个 full；
- 不允许多个 KitNET full 并发；
- 使用实际验证后的特征维度：

```python
KitNET(n=actual_feature_dim, ...)
```

- 不裁剪、不填充、不人为变换维度；
- 不修改固定参数；
- 不修改官方 Kitsune 核心源码；
- 单数据集失败后保存证据并继续下一个数据集。

## 12. 指标规范

### 12.1 Full 必须记录

- `total_rows`
- `grace_rows`
- `execution_rows`
- `runtime_seconds`
- `throughput_rows_per_second`
- `rmse_min`
- `rmse_median`
- `rmse_mean`
- `rmse_std`
- `rmse_p95`
- `rmse_p99`
- `rmse_p99_5`
- `rmse_max`
- `rmse_nan_count`
- `rmse_inf_count`
- `benign_count`
- `attack_count`
- `benign_rmse_statistics`
- `attack_rmse_statistics`
- `roc_auc`
- `pr_auc`
- `attack_prevalence`
- `score_direction`

固定：

```text
score_direction = higher_is_more_anomalous
```

### 12.2 ROC-AUC / PR-AUC 适用条件

仅当执行期同时存在良性和攻击两类标签时计算。

若执行期只有一种标签：

- `roc_auc = null`
- `pr_auc = null`
- 记录不可计算原因

PR-AUC 必须同时记录：

```text
attack_prevalence = attack_count / execution_rows
```

### 12.3 阈值相关指标

在统一阈值协议确定前，不计算或宣称：

- Accuracy
- Precision
- Recall
- F1
- Specificity
- Confusion Matrix

不得自行发明阈值。

## 13. 数据集执行顺序

### 第 1 阶段：工程修复

1. 审计脚本；
2. 修复目录、状态、读取、标签、Git SHA、no-overwrite 等问题；
3. 添加自动化测试；
4. 全部测试通过；
5. 小步 commit；
6. push；
7. 更新 Draft PR #4。

### 第 2 阶段：OS Scan

1. 磁盘检查；
2. 完整流式预检；
3. `smoke-1000`；
4. `smoke-10000`；
5. `full`；
6. 校验全部产物；
7. 更新汇总；
8. commit；
9. push；
10. 更新 PR #4；
11. 记录恢复命令。

### 第 3 阶段：Fuzzing

1. 回归验证带引号标签；
2. 磁盘检查；
3. 完整流式预检；
4. `smoke-1000`；
5. `smoke-10000`；
6. `full`；
7. 校验；
8. commit；
9. push；
10. 更新 PR #4。

### 第 4 阶段：其余六类

逐个按以下流程执行：

```text
磁盘检查
→ 解压
→ 完整流式预检
→ smoke-1000
→ smoke-10000
→ full
→ 产物校验
→ 更新汇总
→ commit
→ push
→ 更新 PR #4
→ 清理可再生成临时解压文件
```

其余六类：

- SSL Renegotiation
- ARP MitM
- SYN DoS
- Active Wiretap
- SSDP Flood
- Video Injection

## 14. 磁盘与解压管理

1. 每次解压前检查可用空间；
2. 每次 full 前再次检查；
3. 解压按数据集串行进行；
4. 不并发解压多个大型数据集；
5. 不并发启动多个 full；
6. 优先保留：
   - 官方压缩包；
   - 最终结果；
   - 配置；
   - 日志；
   - 哈希；
   - Git 记录；
7. 数据集完成并校验后，可删除仅属于该数据集、可重新生成的临时解压副本；
8. 不得删除原始压缩包、成功结果、失败证据、日志和哈希；
9. 不得提交原始 UCI 数据到 Git。

## 15. Git 与 PR 工作流

1. 只在 `exp/overnight-20260712` 工作；
2. 不修改 `main`；
3. 不合并 PR；
4. 不 force push；
5. 不重写历史；
6. 不提交 UCI 原始数据或大型临时文件；
7. 小步 commit；
8. 每完成一个明确阶段就 push；
9. 每完成一个完整数据集就更新 Draft PR #4；
10. PR #4 始终保持 Draft，除非用户明确授权；
11. 每次提交应说明：
    - 修复内容；
    - 实验数据集；
    - smoke/full 状态；
    - 是否修改官方源码；
    - 恢复命令。

## 16. 异常与恢复规则

单数据集失败不得终止其他数据集。

每次异常必须保存：

- `status.json`
- 错误类型
- 错误消息
- 完整 traceback
- 当前数据集
- 当前阶段
- 已完成行数
- 输出目录
- 可恢复命令
- 是否可安全重试

中断后恢复时：

1. 检查当前分支；
2. 检查 worktree；
3. 检查运行进程；
4. 检查现有 status；
5. 检查已有成功结果；
6. 不重复解压已完整存在的数据；
7. 不覆盖已成功 full；
8. 从第一个未完成阶段继续。

## 17. 禁止事项

禁止：

- 修改官方 Kitsune 核心源码；
- 自动调参；
- 修改训练区间；
- 将 115 维裁剪或填充为 100 维；
- 直接修改 main；
- 合并 PR；
- force push；
- 重写历史；
- 提交原始 UCI 数据；
- 删除成功结果；
- 删除失败证据；
- 删除原始压缩包；
- 通过删除正式 `status.json` 强制重跑；
- 在阈值协议确定前宣称 Accuracy/Recall/F1；
- 对 smoke 计算检测指标；
- 多个 full 并发。

## 18. 必须停止并询问用户的情况

仅在以下情况停止：

1. 需要修改官方核心源码；
2. 数据格式无法可靠判断；
3. 磁盘空间不足且无法通过安全清理临时文件解决；
4. 需要改变固定实验参数；
5. 可能覆盖已有成功结果；
6. 需要修改 main；
7. 需要合并 PR；
8. 发现隐私、密钥或账号信息泄露；
9. 数据哈希或文件完整性异常；
10. 训练期前 55,001 行存在攻击样本，且无法确认是否符合官方协议。

## 19. 执行前恢复检查

开始执行前，用不超过 15 行输出：

- 当前分支；
- `git status`；
- `git worktree list`；
- 最新提交；
- 远程状态；
- PR #4 状态；
- 可用磁盘空间；
- 当前数据目录；
- 当前结果目录；
- 当前 Python/KitNET 进程；
- 自动化测试状态；
- 第一项将执行的动作。

随后直接执行，不等待再次确认。

## 20. 最终汇报格式

最终必须汇报：

1. 当前分支；
2. 最新 commit SHA；
3. PR #4 链接和状态；
4. 是否修改官方源码；
5. 自动化测试结果；
6. 九类数据预检总表；
7. smoke-1000 总表；
8. smoke-10000 总表；
9. full 总表；
10. ROC-AUC / PR-AUC 汇总；
11. attack prevalence；
12. 成功/失败/阻塞/中断数量；
13. 总运行时间；
14. 总处理行数；
15. 磁盘占用；
16. 每个异常情况；
17. 下一步精确恢复命令；
18. 下一阶段建议：统一阈值协议、EWMA 改进、最终报告图表。

## 21. 给 Codex 的启动语句

上传本文件后，只需发送：

```text
请完整读取我上传的《Kitsune_剩余实验执行规范.md》。

该文件是本次任务的唯一执行规范，优先级高于此前聊天中不完整或被截断的指令。

先用不超过20行确认：
1. 当前项目状态；
2. 剩余八类数据集；
3. smoke/full目录规则；
4. Git规则；
5. 必须停止的条件。

确认后直接在现有 exp/overnight-20260712 worktree 中执行，不等待我再次确认。
```
