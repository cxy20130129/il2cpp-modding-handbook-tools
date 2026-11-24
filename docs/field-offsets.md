# 字段偏移：从 dump.cs 到可操作的内存布局

Il2CppDumper 的 `dump.cs` 在每个实例字段后面标注了它在对象里的字节位置：

```csharp
public float totalDurationSeconds; // 0x20
private float _remainingSeconds;   // 0x5C
```

这些数字是写 Mod 时最直接的依据——什么时候该读字段、什么时候只能 Hook 方法、两个字段之间为什么隔着一段空隙，都从这里看。本文讲怎么把它们系统性地提出来，以及哪些坑会让偏移表骗你。

## 1. 为什么需要工具

手工整理偏移表有两个问题：一是慢，二是容易把静态字段、常量和实例字段混在一起。以 Iron Nest 的 `CounterBatteryTimer` 为例，`docs/iron-nest-timer-and-tokens.md` 里那张表有 13 行，其中包含 `<Instance>k__BackingField` 这样的静态后备字段。手工抄一遍很容易把 `0x5C` 写成 `0x5D`。

`scripts/field_offsets.py` 直接从 `dump.cs` 生成表，格式和那份文档一致：

```powershell
python .\scripts\field_offsets.py .\dumps\iron-nest\dump.cs CounterBatteryTimer --format markdown
```

输出（节选）：

```markdown
| 偏移 | 增量 | 类型 | 存储 | 字段 | 行号 |
|---|---|---|---|---|---|
| `0x20` | `0x18` | `float` | 实例 | `totalDurationSeconds` | 11394 |
| `0x28` | `0x8` | `UnityEvent` | 实例 | `onTimerStarted` | 11395 |
| `0x30` | `0x8` | `SecondsChangedEvent` | 实例 | `onTimerTick` | 11396 |
```

`--format` 支持四种：

| 格式 | 用途 |
|---|---|
| `text` | 终端里快速看，带对齐 |
| `markdown` | 直接贴进文档，中文表头 |
| `json` | 给别的脚本消费，含修饰符和行号 |
| `csv` | 导进 Excel 做交叉比对 |

类型名支持正则，配合 `--limit` 可以一次扫一类：

```powershell
python .\scripts\field_offsets.py .\dumps\iron-nest\dump.cs "^SleepyNodes\.State_" --regex --format csv > states.csv
```

## 2. 怎么读这张表

### 偏移是相对对象起始地址的

`0x20` 不是"类里第 32 个字节"，而是**从对象首地址算起第 32 字节**。IL2CPP 的对象布局是：

```text
[0x00] Il2CppObject 头部（vtable 指针 + monitor）
[0x10] 基类字段区（MonoBehaviour 等）
[0x18] 本类字段开始
```

所以即使一个类只声明了 3 个字段，第一个字段也可能在 `0x48`——前面是基类的字段。这意味着**不能只看本类的字段数推断布局**。

### 增量列不是字段大小

`delta` 是相邻两个**实例字段**偏移的差，包含了对齐填充。例如：

```text
0x18  byte   flag
0x1C  int    count    delta = 0x4
0x20  string label    delta = 0x4
0x28  double weight   delta = 0x8
```

`label` 到 `weight` 差 8 字节，不是因为 `string` 是 8 字节（它是 8 字节引用，这里刚好），而是因为 `double` 要 8 字节对齐。别用 `delta` 去算 `sizeof(T)`。

反过来，`delta` 很有用的是**找空隙**：如果某个字段后面突然跳了 0x10，说明中间可能有编译器插入的字段、被内联的基类成员，或者你漏看了一个父类。

### 静态字段和常量另算

工具会把 `static` 和 `const` 单独标注，且不给它们算 `delta`。原因：

- `static` 字段存在静态存储区，`// 0x0` 是那个区里的位置，不在对象实例里。
- `const` 在 IL2CPP 里通常被编译期折叠，根本没有运行时存储。
- 两者混进实例字段排序，会把 `delta` 完全打乱。

一个常见坑：`<Instance>k__BackingField` 是自动属性 `Instance` 的后备字段。看到尖括号别以为是 dump 坏了，它就是静态字段。

## 3. 偏移能用来做什么

### 能：判断该 Hook 方法还是直接读字段

- 字段值由 Unity 序列化、在 Inspector 里配置（`totalDurationSeconds`）——直接读字段可以，但改它不如 Hook 使用它的地方稳。
- 字段是运行时状态（`_remainingSeconds`、`endTime`）——读它比每帧 Hook `Update` 便宜得多。
- 字段是 `UnityEvent`（`onTimerTick`）——不要直接调 `Invoke()`，Hook 触发它的入口方法更安全。

### 能：在 Prefix/Postfix 里定位参数来源

`State_StartTimer.OnEnter` 的 Prefix 想改初始时间，先确认 `InitalTime` 在 `0x48` 是节点自己的配置字段，而不是从别的实体传进来的。偏移表能告诉你这一点，但不能告诉你**谁在写这个字段**——那需要反汇编或运行时探针。

### 不能：直接当指针用

BepInEx 6 + Il2CppInterop 下，C# 里访问字段走的是 interop 程序集的正常属性/字段，不需要也不应该手工算地址。偏移表的用途是**理解和验证**，不是拿来写 `Marshal.ReadInt32(ptr + 0x5C)`。-native 指针操作留给 `disasm_method.py` 那种场合。

## 4. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 第一个字段的 `delta` 是 `-` | 它没有前驱实例字段 | 正常。看 `offset` 本身，它包含了头部和基类大小 |
| 字段偏移比本类字段数大很多 | 基类字段占了前面 | 去找基类，对基类再跑一次工具 |
| 表里出现 `// 0x0` 的 `const` | 编译期常量没有实例存储 | 工具已单独标注，忽略即可 |
| 某字段没出现在表里 | 该行没有 `// 0x..` 标注，`find_type` 不认它是字段 | 真实 Il2CppDumper 输出不会这样；如果是自定义 dump，先修格式 |
| 游戏更新后偏移全变 | 类布局变了 | 重新 dump，不要拿旧表猜新版本 |
| 同名类型匹配到多个 | 泛型实例或嵌套类 | 看 `TypeDefIndex` 和源文件行号区分 |

## 5. 和另外两个搜索工具的分工

| 工具 | 回答的问题 |
|---|---|
| `find_type.py` | "这个类/方法/字段在 dump.cs 哪一行？RVA 是多少？" |
| `find_string.py` | "这个 UI 文案/电报文本的字符串字面量在哪？" |
| `field_offsets.py` | "这个类的对象布局长什么样？字段之间怎么排的？" |

典型顺序是：先用 `find_string.py` 从文案反查到类，再用 `find_type.py` 找到方法和 RVA，最后用 `field_offsets.py` 看字段布局决定从哪儿下手。

## 6. 前提与边界

- 输入必须是 Il2CppDumper 标准格式的 `dump.cs`；Il2CppInspector 的输出格式不同，解析规则要改。
- 工具只读文件，不修改 dump，也不接触游戏进程。
- 不处理继承链展开：基类字段要对基类单独跑一次，然后自己合并。
- 不做反作弊绕过，不用于联机游戏。
