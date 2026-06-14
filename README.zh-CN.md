# AutoCAD 中国建筑施工图 Skill

这是一个 `v0.1 alpha` 的 Codex/Agent Skill，用于把文字、带尺寸图片、SVG
或结构化 JSON 转换成可在完整版 AutoCAD 中执行的二维建筑与室内图纸包。

主要能力：

- 建立可配置的中国建筑制图图层、文字、尺寸、图框和布局；
- 生成 Windows/macOS 通用 AutoLISP，不依赖 COM、ActiveX 或 .NET；
- 明确建模房间边界、家具占地、人体活动净空、门扇范围和通行路径；
- 按成人、老年人、儿童及轮椅使用者画像分析空间；
- 输出家具占用率、名义通行保留率、净空冲突和门扇冲突；
- 审查 ASCII DXF 的图层、零长度线和重复线。

Skill 本体位于
[`skills/autocad-cn-drafting-skill`](skills/autocad-cn-drafting-skill)，仓库不会
自动安装到 Codex。

## 快速测试

```bash
SKILL=skills/autocad-cn-drafting-skill

python3 "$SKILL/scripts/validate_project.py" examples/apartment/project.json
python3 "$SKILL/scripts/analyze_space.py" examples/apartment/project.json \
  --output-dir build/space
python3 "$SKILL/scripts/build_package.py" examples/apartment/project.json \
  --output-dir build/apartment
```

在完整版 AutoCAD 中加载生成的 `.lsp`，运行 `CADBUILD`，人工检查后运行
`CADAUDIT`。保存 DWG、导出 ASCII DXF 和 PDF，再使用 `audit_dxf.py` 检查。

## 规则边界

仓库把规则分为：

- `code`：已确认适用于项目的法规或合同要求；
- `baseline`：可配置的人体工程学设计基线，不自动等于强制规范；
- `advisory`：必须由设计人员判断的建议。

本 Skill 不能代替消防、无障碍、结构、机电、法规或注册专业人员审查。
本机自动测试不包含真实 AutoCAD 渲染，因此任何施工用途都必须人工复核。
