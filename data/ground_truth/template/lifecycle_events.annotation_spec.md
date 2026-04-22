# Lifecycle Events 标注规范

## 1. 目标

为时序评测提供极保守的生命周期事件标注。

## 2. 重要说明

O&M 手册通常没有真实历史时间，因此这里的 `timestamp` 只是“相对顺序编码”，不是现实中的维护日期。

## 3. 允许的 `event_type`

- `creation`
- `update`
- `deprecation`
- `replacement`
- `fault_occurrence`
- `maintenance`

## 4. 标注原则

- 手册没有明确对象历史时，不要滥标 `creation`
- 优先标两类：
  - `fault_occurrence`
  - `maintenance` / `replacement`
- 条件语句如果不构成稳定事件，不要写进去

## 5. `object_id` 约定

推荐写法：

- `battery::fault::BATOM_001_outlet_boundary`
- `cnc::component::CNCOM_002_Belleville stack`
- `nev::component::EVMAN_003_HV output stud pocket`

目的不是建本体，而是保证不同窗口下命名稳定、可复核。
