# RN8213/RN8211B 电表校准工具 v2.0 → PyQt5 实施TODO清单 v2

> 基于需求文档《校表软件需求.md》独立实现
>
> 技术栈：PyQt5 + pyserial + 自研DL/T645引擎
>
> 目标：专业校表工具 + 串口通信 + 数据管理

---

## 📋 项目总体进度跟踪

### 已完成 ✅
- [x] 需求文档分析完成
- [x] DL/T645协议研究完成
- [x] 关键算法和协议格式确认完成
- [x] 技术栈可行性确认
- [x] **M1**: 框架搭建完成 - UI骨架、菜单、串口功能、日志系统、对话框全部实现
- [x] **M2**: DL/T645帧构建引擎 - 算法独立实现，100%测试通过

### 待完成 📝
- [ ] **M3**: 校表执行引擎 - 五步校表逻辑、参数计算、设备通信
- [ ] **M4**: 数据管理系统 - 配置持久化、历史记录、报告生成
- [ ] **M5**: 生产环境优化 - 异常处理、重试机制、权限管理
- [ ] **M6**: 现场部署验证 - 实际设备测试、性能优化

---

## 🎯 M1阶段：框架搭建 ✅ 已完成

### 核心成果 ✅
- **UI框架**: PyQt5单页布局，左侧步骤列表 + 右侧通信日志
- **菜单系统**: 完整5级菜单（文件/通讯/参数/自动化/帮助）
- **对话框系统**: 串口配置、标准值输入，参数验证
- **串口基础**: SerialPort类，状态管理，端口枚举
- **日志系统**: 实时显示，自动滚动，时间戳
- **状态管理**: 连接状态、校表进度显示

---

## 🎯 M2阶段：DL/T645帧构建引擎 ✅ 已完成

### 核心成果 ✅
- **算法逆向**: 从参考Excel提取关键算法，实现独立Python版本
- **FrameBuilder引擎**: ExcelEquivalentFrameBuilder类
- **帧解析引擎**: DLT645FrameParser类
- **测试验证**: 100%通过率单元测试 + 数据驱动测试
- **代码质量**: 类型注解、文档完整、错误处理

### 关键算法 ✅
1. **DI字节序翻转**: `reverse_di_bytes()` - 00F81500 → 00 15 F8 00
2. **0x33偏置处理**: `apply_data_offset()` - 每字节+0x33 & 0xFF
3. **校验和计算**: `calculate_checksum()` - 整个帧求和mod 256
4. **帧结构构建**: 完整DL/T645帧组装

### 测试验证 ✅
- **单元测试**: 11个测试全部通过
- **集成测试**: 9个数据驱动测试全部通过
- **边界测试**: 异常输入、错误处理验证
- **算法正确性**: 与参考实现100%一致

---

## 🎯 M3阶段：校表执行引擎 🚧 当前目标

### 3.1 校表步骤引擎
- [ ] **CalibrationStep基类设计**
  ```python
  class CalibrationStep:
      def __init__(self, step_id, name, description)
      def prepare(self, standard_voltage, standard_current)  # 参数准备
      def execute(self, communicator)                        # 执行校表
      def verify(self, response_frame)                       # 结果验证
      def get_result(self)                                   # 获取校正值
  ```

- [ ] **五大校表步骤实现**
  - [ ] **Step1**: 电流有效值offset校正 (空载校正)
    - DI码: 00F81500, 参数: 空载状态标识
  - [ ] **Step2**: 电压电流增益校正 (1.0L标准)
    - DI码: 00F81600, 参数: 标准电压电流值
  - [ ] **Step3**: 功率增益校正
    - DI码: 00F81700, 参数: 功率基准值
  - [ ] **Step4**: 相位补偿校正
    - DI码: 00F81800, 参数: 相位角度
  - [ ] **Step5**: 小电流偏置校正
    - DI码: 00F81900, 参数: 小电流阈值

### 3.2 设备通信管理器
- [ ] **DeviceCommunicator类设计**
  ```python
  class DeviceCommunicator:
      def __init__(self, serial_port, frame_builder, frame_parser)
      def send_calibration_command(self, step, parameters)     # 发送校表命令
      def wait_for_response(self, timeout=3000)               # 等待设备响应
      def verify_response(self, request_frame, response_frame) # 验证响应正确性
      def handle_communication_error(self, error_type)        # 处理通信异常
  ```

- [ ] **通信特性**
  - 超时重试机制 (3次重试，递增延时)
  - 响应帧验证 (地址匹配、控制码检查)
  - 错误分类处理 (超时/校验/设备错误)
  - 通信状态跟踪 (空闲/忙碌/错误)

### 3.3 参数计算引擎
- [ ] **ParameterCalculator类设计**
  ```python
  class ParameterCalculator:
      def calculate_voltage_params(self, standard_voltage)     # 电压参数计算
      def calculate_current_params(self, standard_current)     # 电流参数计算
      def calculate_power_params(self, voltage, current)       # 功率参数计算
      def encode_to_dl645_format(self, physical_value)         # 物理值编码
      def decode_from_dl645_format(self, dl645_data)           # DL/T645解码
  ```

- [ ] **计算特性**
  - 标准值范围验证 (电压90-300V，电流0-200A)
  - 精度控制 (浮点运算，合理舍入)
  - 单位转换 (物理量到协议数据格式)
  - 误差分析 (计算偏差百分比)

### 3.4 执行策略系统
- [ ] **CalibrationExecutor类设计**
  ```python
  class CalibrationExecutor:
      def execute_single_step(self, step_id)                  # 单步执行
      def execute_selected_steps(self, step_list)             # 批量执行
      def execute_one_click_calibration(self)                 # 一键校表
      def handle_step_failure(self, step, error)              # 失败处理
  ```

- [ ] **执行特性**
  - 步骤状态管理 (pending/running/success/failed/skipped)
  - 进度回调机制 (UI实时更新)
  - 异常恢复策略 (重试/跳过/终止)
  - 执行历史记录 (时间、参数、结果)

### 3.5 集成到主窗口
- [ ] **主窗口集成**
  - 替换现有模拟执行逻辑
  - 集成真实校表执行引擎
  - 实时显示执行进度和结果
  - 错误处理和用户提示

---

## 🎯 M4阶段：可维护性优化与扩展性设计

### 4.1 轻量级配置管理
- [ ] **ConfigManager类设计**
  ```python
  class ConfigManager:
      def save_serial_config(self, config)          # 串口配置保存
      def load_serial_config(self)                  # 串口配置加载
      def save_standard_values(self, values)        # 标准值保存
      def save_user_preferences(self, preferences)  # 用户偏好保存
      def save_session_data(self, session)          # 会话数据保存
  ```

- [ ] **配置特性**
  - JSON文件存储，轻量级无依赖
  - 配置版本管理和兼容性检查
  - 默认配置和恢复机制
  - 配置导入导出 (便于部署)

### 4.2 简化记录系统
- [ ] **SessionRecorder类设计**
  ```python
  class SessionRecorder:
      def start_session(self)                       # 开始校表会话
      def record_step_result(self, step, result)    # 记录步骤结果
      def end_session(self, summary)                # 结束会话
      def export_session_report(self, format)       # 导出会话报告
  ```

- [ ] **记录特性**
  - JSON文件存储 (无数据库依赖)
  - 按会话组织记录
  - 简单的成功率统计
  - 文本/CSV格式导出

### 4.3 台体控源扩展架构
- [ ] **设备抽象层设计**
  ```python
  class DeviceInterface(ABC):
      def connect(self, config)                     # 连接设备
      def send_command(self, command)               # 发送命令
      def read_response(self, timeout)              # 读取响应
      def disconnect(self)                          # 断开连接

  class ElectricMeterDevice(DeviceInterface):       # 电表设备实现
  class PowerSourceDevice(DeviceInterface):        # 台体控源设备预留
  ```

- [ ] **扩展特性**
  - 统一设备接口 (便于添加台体控源)
  - 设备类型自动识别
  - 多设备会话管理
  - 设备状态监控

### 4.4 增强的错误处理
- [ ] **ErrorHandler类设计**
  ```python
  class ErrorHandler:
      def handle_communication_error(self, error)   # 通信错误处理
      def handle_device_error(self, error)          # 设备错误处理
      def handle_parameter_error(self, error)       # 参数错误处理
      def generate_error_report(self, session)      # 错误报告生成
  ```

- [ ] **错误处理特性**
  - 分类错误处理策略
  - 用户友好的错误提示
  - 错误恢复建议
  - 详细错误日志记录

### 4.5 模板系统简化
- [ ] **ParameterPresets类设计**
  ```python
  class ParameterPresets:
      def load_presets(self)                        # 加载预设参数
      def save_preset(self, name, params)           # 保存参数预设
      def apply_preset(self, name)                  # 应用预设
      def validate_preset(self, preset)             # 预设验证
  ```

- [ ] **预设特性**
  - 内置常用参数组合
  - 用户自定义预设
  - 预设参数验证
  - 快速切换功能

---

## 🎯 M5阶段：生产环境优化

### 5.1 异常处理系统
- [ ] **统一异常处理框架**
- [ ] **错误分类和处理策略**
- [ ] **用户友好的错误提示**
- [ ] **异常日志和诊断信息**

### 5.2 重试机制
- [ ] **智能重试策略**
- [ ] **重试历史记录**
- [ ] **重试成功率统计**

### 5.3 权限管理
- [ ] **用户角色定义** (操作员/工程师)
- [ ] **功能权限控制**
- [ ] **敏感操作审计**

### 5.4 性能优化
- [ ] **内存管理优化**
- [ ] **UI响应性优化**
- [ ] **通信效率优化**

---

## 🎯 M6阶段：现场部署验证

### 6.1 实际设备测试
- [ ] **真实电表连接测试**
- [ ] **长时间稳定性测试**
- [ ] **多设备兼容性测试**

### 6.2 用户验收测试
- [ ] **操作流程验证**
- [ ] **界面易用性测试**
- [ ] **错误处理验证**

### 6.3 性能基准测试
- [ ] **校表精度验证**
- [ ] **通信速度测试**
- [ ] **系统资源占用测试**

---

## 📝 开发规范

### 代码质量要求
- **类型注解**: 所有公共API必须有类型注解
- **文档字符串**: 所有类和公共方法必须有文档
- **单元测试**: 核心逻辑必须有对应测试
- **错误处理**: 异常情况必须妥善处理

### 可维护性原则
- **单一职责**: 每个类只负责一个明确的功能
- **依赖注入**: 避免硬编码依赖，使用接口和注入
- **配置化**: 避免魔数，重要参数可配置
- **模块化**: 功能模块间低耦合，高内聚

### 测试策略
- **单元测试**: 针对单个函数和类方法
- **集成测试**: 针对模块间协作
- **系统测试**: 针对完整功能流程
- **性能测试**: 针对关键路径和瓶颈

---

> **当前状态**: M2阶段完成，准备进入M3阶段
>
> **M3目标**: 实现完整的校表执行引擎，支持真实设备通信
>
> **设计原则**: 高可维护性、模块化、可测试、生产就绪