# 第三方组件与工程贡献边界

本工程通过正常 Python 依赖安装复用下列组件，没有将第三方源码复制为项目自研文件。

| 组件 | 包与版本约束 | 许可 | 用途与官方来源 |
| --- | --- | --- | --- |
| PyArg | `python-argumentation==2.0.2` | MIT | 生产 grounded 论证求解；https://github.com/DaphneOdekerken/PyArg |
| NetworkX | `networkx==3.6.1` | BSD-3-Clause | 论证图结构、循环组、攻击和防御解释；https://github.com/networkx/networkx |
| Pydantic | `pydantic>=2.7,<3`，具体版本见 `backend/uv.lock` | MIT | 规则配置校验和不可变模型；https://github.com/pydantic/pydantic |

许可随各依赖的标准分发包提供；本文为组件来源说明，不替代上游许可文本。其他既有组件继续通过原有依赖文件声明。

grounded / Dung 论证语义、图算法及上述组件均不属于团队原创。项目贡献是视频证据映射、来源别名合并、事件和动作隔离、领域规则配置与校验、模型关系门控、人工复核分流、冻结输入移除检验、业务报告和可复现验证。

Argdown、OPA 决策日志仍属于设计参考，本工程没有接入它们的运行引擎；SafeWatch 未在本轮安装、训练或运行。本轮也没有使用 PyArg 的 ASPIC+ 功能。
