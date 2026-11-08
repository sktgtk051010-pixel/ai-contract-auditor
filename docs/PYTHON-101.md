# Python 速成（给会 C 的人）

这份文档只讲本项目用到的语法，全部用 C 做对照。读完能看懂 `src/` 下的每个文件。

---

## 0. 怎么运行

```bash
python src/scan.py --target D:\project\src
```

C 要 `gcc main.c -o main && ./main`，Python 不用编译，`python 文件名.py` 直接跑。

带 `--target` 这种叫命令行参数，由 `argparse` 模块解析（后面讲）。

---

## 1. 变量：不用写类型

```python
count = 0          # int
name = "vault"     # str
ratio = 1.5        # float
flag = True        # bool（注意大写 T）
```

对应 C：

```c
int count = 0;
char *name = "vault";
float ratio = 1.5;
int flag = 1;
```

Python 变量就是一个名字，指向一个对象。类型跟着值走，不跟着名字走。

判断类型用 `type(x)`，类似 C 的 `sizeof` 只能看大小，Python 能直接看类型名。

---

## 2. 缩进就是花括号

```python
if count > 0:
    print("positive")     # 缩进 4 格 = 属于 if 内部
else:
    print("not positive")
```

C 用 `{}` 划定范围，Python 用**缩进**。冒号 `:` 表示"下面开始一个块"。

**缩进错了程序就错**，而且不一定报错，可能悄悄算错。这是 Python 最常见的坑。

---

## 3. print 就是 printf

```python
print("hello")                    # 相当于 printf("hello\n")
print("files =", 15)              # 多个值用逗号，自动加空格
print(f"files = {15}")            # f-string，{} 里可以放变量
```

f-string 是最好用的：

```python
name = "vault"
print(f"scanning {name}")         # 输出：scanning vault
```

相当于 C 的 `printf("scanning %s\n", name)`，但不用记 `%s` `%d`。

---

## 4. 列表 list ≈ 数组（但能自动变长）

```python
items = []                 # 空列表
items.append("a")          # 尾部加一个
items.append("b")
print(items)               # ['a', 'b']
print(len(items))          # 2
print(items[0])            # 'a'，下标从 0 开始
```

C 里要开固定大小数组 `char *items[10]` 再自己记长度，Python 自动扩容、自动记长度。

遍历：

```python
for item in items:         # 相当于 for (i=0; i<n; i++) 访问 items[i]
    print(item)
```

---

## 5. 字典 dict ≈ 用字符串当索引的数组

```python
person = {"name": "alice", "age": 20}
print(person["name"])      # alice
person["age"] = 21         # 修改
person["city"] = "changsha"  # 新增
```

C 里没有现成的键值容器，要自己写哈希表。Python 内置。

**本项目大量用字典**：`scan.json` 里每个文件、每个函数都是一个字典。

---

## 6. 函数：def 开头，不用写返回类型

```python
def add(a, b):
    return a + b

print(add(1, 2))           # 3
```

C：

```c
int add(int a, int b) { return a + b; }
```

Python 不声明参数类型和返回类型，传什么用什么。

---

## 7. import ≈ #include

```python
import json                # 相当于 #include <stdio.h>，但不用链接
from pathlib import Path   # 从 pathlib 里只拿 Path 这一个东西
```

用法带前缀：

```python
json.loads(text)           # json 模块里的 loads 函数
Path("build")              # Path 类
```

---

## 8. if / for / while 对照

```python
# C: for (int i = 0; i < 10; i++) printf("%d\n", i);
for i in range(10):
    print(i)

# C: while (x > 0) x--;
while x > 0:
    x = x - 1

# C: if (a == 1) {...} else if (a == 2) {...} else {...}
if a == 1:
    ...
elif a == 2:
    ...
else:
    ...
```

`range(10)` 生成 0..9。`range(1, 6)` 生成 1..5。

**注意 Python 没有 `i++`**，要写 `i = i + 1` 或 `i += 1`。

---

## 9. 读文件

```python
text = open("a.txt", "r", encoding="utf-8").read()
```

更现代的写法（本项目用的）：

```python
from pathlib import Path
text = Path("a.txt").read_text(encoding="utf-8")
```

写文件：

```python
Path("out.txt").write_text("hello", encoding="utf-8")
```

`encoding="utf-8"` 必须写，否则中文可能乱码——相当于 C 里要指定字节编码。

---

## 10. JSON：本项目的数据格式

```python
import json

# 字符串 -> Python 字典
data = json.loads('{"a": 1}')        # data 是 dict，data["a"] 是 1

# Python 字典 -> 字符串
text = json.dumps(data, indent=2)    # indent=2 表示缩进美化
```

读写文件通常连起来：

```python
data = json.loads(Path("build/scan.json").read_text(encoding="utf-8"))
Path("out.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

`ensure_ascii=False` 让中文原样写出，不变成 `\u4e2d`。

---

## 11. 异常 try/except

```python
try:
    x = int("abc")        # 这里会失败
except ValueError:
    print("不是数字")      # 失败时走这里
```

相当于 C 里检查返回值：

```c
if (sscanf(s, "%d", &x) != 1) { printf("bad\n"); }
```

Python 用"抛出异常"表示失败，不用返回错误码。`analyze.py` 调 API 失败就靠这个重试。

---

## 12. 列表推导（看着怪，其实就是循环）

```python
names = [f["name"] for f in files]
```

等价于：

```python
names = []
for f in files:
    names.append(f["name"])
```

意思是"对 files 里每个 f，取 f['name']，组成一个新列表"。

`scan.py` 里有：

```python
files = [scan_file(p, root) for p in sorted(root.rglob("*.sol"))]
```

翻译：找出所有 .sol 文件，对每个文件调用 `scan_file`，把结果装进列表。

---

## 13. 模块入口 `if __name__ == "__main__"`

```python
if __name__ == "__main__":
    main()
```

意思：**只有直接运行这个文件时才执行 main()**；被别的文件 import 时不执行。

相当于 C 的 `int main()`，但 Python 允许一个文件既当库又当程序。

---

## 14. 路径：pathlib

```python
from pathlib import Path

p = Path("build") / "scan.json"    # 拼路径，自动处理分隔符
p.parent.mkdir(parents=True, exist_ok=True)   # 建目录，已存在不报错
p.exists()                          # 文件在不在
p.read_text()                       # 读内容
```

`/` 在这里不是除法，是"拼路径"。Windows 和 Linux 都能用，不用纠结 `\` 还是 `/`。

---

## 15. 常用内置函数

| Python | C 类比 | 作用 |
|---|---|---|
| `len(x)` | 自己记的长度 | 元素个数 |
| `sum(x)` | 循环累加 | 求和 |
| `max(x)` / `min(x)` | 循环比较 | 最大/最小 |
| `sorted(x)` | qsort | 排序，返回新列表 |
| `enumerate(x)` | `for(i=0;...)` | 同时拿下标和值 |
| `any(x)` / `all(x)` | — | 任一为真 / 全部为真 |

`enumerate` 例子：

```python
for i, item in enumerate(items, start=1):
    print(i, item)
```

相当于 C 里同时用 `i` 和 `items[i]`。

---

## 16. 几个会坑你的地方

| 坑 | 说明 |
|---|---|
| 缩进混用空格和 Tab | 报 `IndentationError`，统一用 4 个空格 |
| 路径反斜杠 | `"D:\a\b"` 里 `\b` 是转义符，用 `r"D:\a\b"` 或 `/` |
| 中文输出乱码 | 读写文件都带 `encoding="utf-8"` |
| 改列表时遍历 | 边遍历边删会跳元素，先复制一份 |
| 字典取不存在的键 | 会抛 `KeyError`，用 `.get("k", 默认值)` |

---

## 17. 读完这份，怎么验证自己看懂了

打开 `src/scan.py`，从第 1 行往下读，遇到不认识的语法回这份文档查。能独立说出下面三行在干什么，就算过关：

```python
raw = path.read_text(encoding="utf-8", errors="replace")
text = strip_comments(raw)
contracts = parse_contracts(text)
```

答案：

1. 读文件全部内容，编码 UTF-8，读不了的地方用替换字符而不是崩溃
2. 把注释挖掉（换成空格，保持行号不变）
3. 从处理后的文本里找出所有合约名和行号
