---
name: datetime-skill
description: >-
  提供日期时间工具，包括获取当前时间和计算日期差。
  当用户询问当前时间、日期或需要日期相关计算时使用。
metadata:
  author: MyClaw
  version: "1.0.0"
---

# DateTime Skill

提供日期和时间相关的实用工具。

## 调用方式

通过 `shell_executor` 执行以下命令（脚本路径相对于 backend 工作目录）：

### get_current_time

获取指定时区的当前日期和时间。

```bash
python skills/datetime-skill/scripts/tools.py get_current_time --timezone=Asia/Shanghai
```

**参数：**
- `--timezone`：IANA 时区标识符，默认 `Asia/Shanghai`。常用值：`US/Eastern`、`Europe/London`、`UTC`

**输出示例：**
```
2026-02-22 21:45:30 CST (UTC+0800)
```

### calculate_date_diff

计算两个日期之间的天数差。

```bash
python skills/datetime-skill/scripts/tools.py calculate_date_diff --date1=2024-01-01 --date2=2024-12-31
```

**参数：**
- `--date1`：第一个日期，格式 `YYYY-MM-DD`（必填）
- `--date2`：第二个日期，格式 `YYYY-MM-DD`（必填）

**输出示例：**
```
2024-01-01 和 2024-12-31 之间相差 365 天
```

## 注意事项

- 支持所有 IANA 时区标识符
- 日期差计算使用绝对值，参数顺序不影响结果
