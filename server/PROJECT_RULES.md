# Server 子工程 — 局部规则（补充）

本文件只补充服务端工程特有信息，不得与工作区总规范冲突：
- 总规范：../SPECS/OPERATING_RULES.md

## 技术栈（按当前工程）
- 语言/框架：Python + FastAPI
- Web Server：Uvicorn
- 第三方：garminconnect
- 配置管理：`config/config.yaml` + 环境变量（`set_env.sh`）

## 入口与常用命令
- 启动（脚本）：`bash scripts/start_server.sh`
- 启动（直跑）：`python -m uvicorn server.app:app --host 127.0.0.1 --port 8010`
- API 冒烟：`bash scripts/test_alignment_api.sh`
- 端到端测试：`bash scripts/test_server_api.sh`

## API 契约要求（建议）
- 接口变更必须同步：
  - 路由/controller
  - DTO/Schema（请求/响应）
  - 最小测试（单测/集成测试至少一种）

## 质量底线
- 不打印敏感信息（token/邮箱/密码）
- 错误返回不要泄露内部堆栈到客户端
- 参数校验与鉴权必须稳定
