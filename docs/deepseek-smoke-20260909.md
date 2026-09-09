# 两例 × 五设置 × 三轮诊断测试（2026-09-09）

本次完成 **10 场生成、90 个 agent-turn 的诊断输出**。模型响应均报告 `deepseek-v4-flash`，有效生成请求 90/90 成功。全连接、同步三轮；每轮三个 agent 均输出 assessment 与一个 principal diagnosis。两例来自冻结的 MedCaseReasoning 24 例计划：PMC12000239（Moyamoya disease）及 PMC10825882（phosphaturic mesenchymal tumor）。

病例原文、逐轮诊断、实际可见输入及验证抽取保存在本地 `runs/deepseek-smoke-20260909-v2/`，不进入 Git。英文检查页是该目录的 `diagnosis-viewer.html`，逐轮表为 `diagnoses.csv`，离线检查结果为 `checks.json`。HTML 已通过静态语法检查，没有完成浏览器视觉验收。

## 模型范围与凭据

用户澄清的正式默认设置为：**DeepSeek V4 Flash 用于 agent 推理，MiniMax M2.5 用于抽取与第二次原子化，匹配保留本地 Qwen3-14B，优先使用 OpenCode API 2。** 已写入全部尚未执行的模板／24 例计划。凭据变量是 `OPENCODE_API_KEY_2`，不存在时明确失败，不自动改用第一个 key。

本次已经生成的 90 个诊断和两份 DeepSeek 抽取使用了澄清前的 API 1 配置，原始 YAML 保持不变。用户允许将已有 DeepSeek 抽取作为观察用验证；没有把它当作正式抽取默认。两份额外 API 匹配已取消，无完整匹配结果，其余八场未做抽取／匹配。不将这些状态表述为端到端全管线通过。

最初两场因缺少新网关会话头而在生成前失败，原始目录 `runs/deepseek-smoke-20260909/` 保留。修复客户端后，全部十场用同一协议从头生成。新客户端发送自己的 User-Agent 和每个 agent 对话稳定的 `x-opencode-session`，与请求重试共用会话标识，不共享生成响应缓存。[官方接入要求](https://opencode.ai/docs/go/#where-can-i-use-it)

## 每轮诊断方向

下表计数表示三个 principal diagnosis 中有几个与参考**诊断方向**一致，是对本次 90 个答案逐项阅读后的描述，不是经过医生验证的临床准确率。Moyamoya disease/syndrome 属于同一诊断方向；TIO 若没有指出 PMT 则标为更宽的综合征，单独保留，不算精确目标命中。

| 病例 | 设置 | R1 | R2 | R3 |
|---|---|---:|---:|---:|
| Moyamoya | shared-generic | 3/3 | 3/3 | 3/3 |
| Moyamoya | shared-specialist | 3/3 | 3/3 | 3/3 |
| Moyamoya | split-generic | 2/3 | 2/3 | 3/3 |
| Moyamoya | split-specialist | 2/3 | 2/3 | 3/3 |
| Moyamoya | split-mismatched | 2/3 | 3/3 | 3/3 |
| PMT | shared-generic | 3/3 | 3/3 | 3/3 |
| PMT | shared-specialist | 3/3 | 3/3 | 3/3 |
| PMT | split-generic | 2/3 | 3/3 | 3/3 |
| PMT | split-specialist | 1/3 | 3/3 | 3/3 |
| PMT | split-mismatched | 2/3 | 3/3 | 3/3 |

合计为 R1 **23/30**、R2 **28/30**、R3 **30/30**。R1 另有一个给出更宽 TIO 综合征的答案。这里只有两个独立病例、每条件一次抽样，不能据此判断 specialist 优于 generic，或错配改善系统。共享信息在这两例的第一轮就已给出参考方向，说明这两例适合检查传递和修正机制，但尚未证明可以区分最终准确率。

## 检查发现

1. **信息到达不保证被接受。** Moyamoya 的 split-generic 与 split-specialist 中，检验 agent C 在 R2 已收到两位同伴的临床／影像输出，包括儿童身份、偏瘫与血管病变，却称其可能属于另一位患者，保留原先血液肿瘤方向，R3 才修正。这不是丢消息。后续协议应明确所有分区和同伴讨论属于同一患者；本次没有中途修改提示词来消除这个现象。
2. **分信息也剥离了基本共同背景。** 检验和影像分区通常不含原文开头的年龄、性别和主诉。这是当前分区的真实性质，不应被误当成纯专业能力差异。后续可以把明确界定的共同元数据发给所有人，并在五个条件一致控制；不要只对某一设置额外补充。
3. **字符串多数票产生假平局。** PMT 的 split-generic 最后一轮三人均给出 PMT/TIO 方向，但措辞不同，当前字符串 majority 返回平局／空聚合答案。保留原始 outcome；未通过事后字符串清洗将它伪装成已验证的临床评分。正式实验前需要冻结语义诊断归一与聚合规则。
4. **部分解释加入了输入没有明确提供的内容。** 例如一个临床 agent 把“已开始使用某治疗”写成“此前对治疗有反应”，一个影像 agent 加入原文没有描述的形态修饰。这些应区别于正确的最终诊断进行检查；不能用最后答案正确来推断整段事实都正确。
5. **DeepSeek 抽取出现输入／输出边界错误。** shared-specialist 的 A|2 输出没有逐项复述完整原始病例，但抽取父事实已经引入了仅在其输入上下文中的病史、检验与影像条目。错误发生在抽取阶段，随后原子化保留了它。这会虚构事实复述或传输，不能用于 fact-flow 结论。
6. **原子化和 quote 也需验证。** 有的引用被改写为省略号形式或补了前面的修饰词，因而不再是原文连续跨度；一个备选诊断的 disjunction 被拆成两个分别带“most likely”的命题。结构化 JSON 合法不能替代语义与引用验证。

## 两份抽取验证

两份均为 Moyamoya 病例、DeepSeek V4 Flash：每场 10 个来源文本单元＋9 个输出单元。使用相同抽取及原子化提示词，所有 parent 做第二次原子化。这些数字是 **mentions／引用出现位置**，不是匹配后的 unique facts。

| 设置 | 文本单元 | 初始 parent | 原子化后 mentions | 引用已定位 | 引用未定位 |
|---|---:|---:|---:|---:|---:|
| shared-generic | 19 | 255 | 261 | 253 | 8 |
| shared-specialist | 19 | 321 | 333 | 278 | 57 |

合计 594 mentions，596 个引用位置，其中 65 个未定位，约 **10.9%**。这些引用缺陷不全意味着命题为假，但不能当作可靠输出出处；一个集中导入输入的记录占 shared-specialist 的 43 个未定位 mentions。两个抽取阶段在技术上完成，**语义质量检查没有通过**。后续换回 MiniMax 后仍应重新检查边界、quote、指代和 disjunction，不能从换模型直接推定问题消失。

第一场抽取发生一次连接／DNS 故障，完整失败尝试保留在 `extraction-failed-attempt1/`。恢复后从头重跑全部文本单元，没有复用失败阶段的部分记录。取消的匹配目录标记 `cancelled`；不能把尚未生成的关系计为零条传输或 UNRELATED。

## 可靠性、用量与验证边界

- 有效生成：90 次成功 HTTP 请求，响应模型全部为 DeepSeek V4 Flash；总计 94,710 input tokens、19,176 output tokens。各场生成 wall time 合计约 116.7 秒，不含准备、失败接入和抽取。
- 抽取验证含失败整阶段及重试：136 条落盘调用记录，132 成功、4 传输失败；已记录用量 304,321 input、170,287 output tokens。
- 已取消的 API 匹配：43 条已完成调用记录，已记录用量 54,305 input、42,040 output tokens。取消时可能存在未落盘的在途请求，因此不声称这是实际消耗的精确总数。
- 已验证：五个条件仅改变声明的角色／分信息维度；所有轮次均有诊断；R1 独立，R2/R3 恰好收到两位同伴上一轮；自身历史与来源可见性正确；更改 metadata/reference 不改变 agent 输入；病例与 trace 校验和一致。
- 38 项离线回归测试通过；24 例后续计划的 120 份 YAML 也通过一致性复核。
- 本次没有运行默认本地 Qwen 匹配，也没有在 API 2 上测试 MiniMax。不能把两个抽取验证样本或诊断方向收敛当作完整测量工具的质量保证。
