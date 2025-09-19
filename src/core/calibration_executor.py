#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校表执行器 - M3阶段
统一管理校表步骤的执行策略和流程控制
支持单步执行、批量执行、一键校表等多种执行模式
"""

from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, Future

from .calibration_step import (
    CalibrationStep, CalibrationParameters, StepResult, StepStatus,
    create_all_calibration_steps
)
from .device_communicator import DeviceCommunicator
from .parameter_calculator import ParameterCalculator


class ExecutionMode(Enum):
    """执行模式"""
    SINGLE_STEP = "single_step"        # 单步执行
    SELECTED_STEPS = "selected_steps"  # 选择步骤执行
    FULL_AUTO = "full_auto"           # 一键全自动校表


class ExecutionStatus(Enum):
    """执行状态"""
    IDLE = "idle"                     # 空闲
    RUNNING = "running"               # 运行中
    PAUSED = "paused"                # 暂停
    COMPLETED = "completed"          # 完成
    FAILED = "failed"                # 失败
    CANCELLED = "cancelled"          # 取消


@dataclass
class ExecutionConfig:
    """执行配置"""
    mode: ExecutionMode = ExecutionMode.SINGLE_STEP
    stop_on_error: bool = False       # 出错时是否停止
    auto_retry_failed: bool = True    # 自动重试失败步骤
    max_step_retries: int = 2         # 步骤最大重试次数
    step_delay_ms: int = 500          # 步骤间延时
    progress_callback: Optional[Callable] = None  # 进度回调函数

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode.value,
            'stop_on_error': self.stop_on_error,
            'auto_retry_failed': self.auto_retry_failed,
            'max_step_retries': self.max_step_retries,
            'step_delay_ms': self.step_delay_ms
        }


@dataclass
class ExecutionResult:
    """执行结果"""
    execution_id: str
    status: ExecutionStatus
    executed_steps: List[str] = field(default_factory=list)
    successful_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    total_time_ms: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_id': self.execution_id,
            'status': self.status.value,
            'executed_steps': self.executed_steps,
            'successful_steps': self.successful_steps,
            'failed_steps': self.failed_steps,
            'skipped_steps': self.skipped_steps,
            'step_results': {step_id: result.to_dict() for step_id, result in self.step_results.items()},
            'total_time_ms': self.total_time_ms,
            'error_message': self.error_message,
            'success_rate': len(self.successful_steps) / len(self.executed_steps) * 100 if self.executed_steps else 0
        }


class CalibrationExecutor:
    """校表执行器

    负责协调校表步骤的执行:
    - 步骤状态管理
    - 执行策略控制
    - 进度回调机制
    - 异常恢复处理
    """

    def __init__(self, communicator: DeviceCommunicator, config: Optional[ExecutionConfig] = None):
        """初始化执行器

        Args:
            communicator: 设备通信器
            config: 执行配置
        """
        self.communicator = communicator
        self.config = config or ExecutionConfig()
        self.parameter_calculator = ParameterCalculator()

        # 创建校表步骤
        self.calibration_steps = {step.step_id: step for step in create_all_calibration_steps()}

        # 执行状态
        self.current_status = ExecutionStatus.IDLE
        self.current_execution: Optional[ExecutionResult] = None
        self.execution_thread: Optional[threading.Thread] = None
        self.stop_requested = False

        # 日志
        self.logger = logging.getLogger("CalibrationExecutor")

        # 执行历史
        self.execution_history: List[ExecutionResult] = []
        self.execution_counter = 0

    def execute_single_step(self, step_id: str,
                           calibration_params: CalibrationParameters) -> StepResult:
        """单步执行

        Args:
            step_id: 步骤ID
            calibration_params: 校表参数

        Returns:
            步骤执行结果
        """
        self.logger.info(f"开始单步执行: {step_id}")

        step = self.calibration_steps.get(step_id)
        if not step:
            raise ValueError(f"未找到步骤: {step_id}")

        # 重置步骤状态
        step.reset()

        try:
            # 执行步骤
            result = step.execute(self.communicator, calibration_params)

            # 处理失败的步骤
            if result.status == StepStatus.FAILED and self.config.auto_retry_failed:
                result = self._retry_step(step, calibration_params, self.config.max_step_retries)

            self.logger.info(f"单步执行完成: {step_id}, 状态: {result.status.value}")
            return result

        except Exception as e:
            error_msg = f"单步执行异常: {str(e)}"
            self.logger.error(error_msg)
            return StepResult(
                status=StepStatus.FAILED,
                error_message=error_msg
            )

    def execute_selected_steps(self, step_ids: List[str],
                              calibration_params: CalibrationParameters) -> ExecutionResult:
        """批量执行选定步骤

        Args:
            step_ids: 步骤ID列表
            calibration_params: 校表参数

        Returns:
            执行结果
        """
        self.logger.info(f"开始批量执行: {step_ids}")

        # 创建执行结果
        execution_id = f"batch_{self.execution_counter}"
        self.execution_counter += 1

        execution_result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING
        )

        self.current_execution = execution_result
        self.current_status = ExecutionStatus.RUNNING

        start_time = time.time()

        try:
            for step_id in step_ids:
                if self.stop_requested:
                    execution_result.status = ExecutionStatus.CANCELLED
                    break

                # 执行步骤
                step_result = self._execute_step_with_tracking(step_id, calibration_params, execution_result)

                # 检查是否需要停止
                if (step_result.status == StepStatus.FAILED and
                    self.config.stop_on_error):
                    execution_result.status = ExecutionStatus.FAILED
                    execution_result.error_message = f"步骤{step_id}执行失败，停止后续执行"
                    break

                # 步骤间延时
                if self.config.step_delay_ms > 0:
                    time.sleep(self.config.step_delay_ms / 1000.0)

            # 完成执行
            if execution_result.status == ExecutionStatus.RUNNING:
                execution_result.status = ExecutionStatus.COMPLETED

            execution_result.total_time_ms = int((time.time() - start_time) * 1000)

            self.logger.info(f"批量执行完成: {execution_result.status.value}")
            return execution_result

        except Exception as e:
            error_msg = f"批量执行异常: {str(e)}"
            self.logger.error(error_msg)

            execution_result.status = ExecutionStatus.FAILED
            execution_result.error_message = error_msg
            execution_result.total_time_ms = int((time.time() - start_time) * 1000)

            return execution_result

        finally:
            self.current_status = ExecutionStatus.IDLE
            self.execution_history.append(execution_result)

    def execute_one_click_calibration(self, calibration_params: CalibrationParameters) -> ExecutionResult:
        """一键校表

        Args:
            calibration_params: 校表参数

        Returns:
            执行结果
        """
        self.logger.info("开始一键校表")

        # 获取所有步骤ID
        all_step_ids = list(self.calibration_steps.keys())

        # 设置全自动模式
        original_config = self.config
        self.config = ExecutionConfig(
            mode=ExecutionMode.FULL_AUTO,
            stop_on_error=False,  # 全自动模式不因单步错误停止
            auto_retry_failed=True,
            max_step_retries=2,
            step_delay_ms=1000,   # 增加延时确保稳定性
            progress_callback=original_config.progress_callback
        )

        try:
            # 执行所有步骤
            result = self.execute_selected_steps(all_step_ids, calibration_params)
            result.execution_id = f"one_click_{self.execution_counter - 1}"

            self.logger.info(f"一键校表完成: {result.status.value}")
            return result

        finally:
            # 恢复原配置
            self.config = original_config

    def execute_async(self, step_ids: List[str],
                     calibration_params: CalibrationParameters) -> Future[ExecutionResult]:
        """异步执行

        Args:
            step_ids: 步骤ID列表
            calibration_params: 校表参数

        Returns:
            Future对象
        """
        if self.current_status != ExecutionStatus.IDLE:
            raise RuntimeError("执行器忙碌中，无法启动新的异步执行")

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.execute_selected_steps, step_ids, calibration_params)

        return future

    def _execute_step_with_tracking(self, step_id: str, calibration_params: CalibrationParameters,
                                  execution_result: ExecutionResult) -> StepResult:
        """执行步骤并跟踪结果

        Args:
            step_id: 步骤ID
            calibration_params: 校表参数
            execution_result: 执行结果对象

        Returns:
            步骤结果
        """
        step = self.calibration_steps[step_id]

        # 进度回调
        if self.config.progress_callback:
            self.config.progress_callback(step_id, StepStatus.RUNNING, None)

        # 执行步骤
        result = self.execute_single_step(step_id, calibration_params)

        # 更新执行结果
        execution_result.executed_steps.append(step_id)
        execution_result.step_results[step_id] = result

        if result.status == StepStatus.SUCCESS:
            execution_result.successful_steps.append(step_id)
        elif result.status == StepStatus.FAILED:
            execution_result.failed_steps.append(step_id)
        elif result.status == StepStatus.SKIPPED:
            execution_result.skipped_steps.append(step_id)

        # 进度回调
        if self.config.progress_callback:
            self.config.progress_callback(step_id, result.status, result)

        return result

    def _retry_step(self, step: CalibrationStep, calibration_params: CalibrationParameters,
                   max_retries: int) -> StepResult:
        """重试失败步骤

        Args:
            step: 校表步骤
            calibration_params: 校表参数
            max_retries: 最大重试次数

        Returns:
            步骤结果
        """
        for retry_count in range(max_retries):
            self.logger.info(f"重试步骤 {step.step_id} (第{retry_count + 1}次)")

            # 重置并重试
            step.reset()
            result = step.execute(self.communicator, calibration_params)

            if result.status == StepStatus.SUCCESS:
                self.logger.info(f"步骤重试成功: {step.step_id}")
                return result

            # 重试间隔
            time.sleep(0.5)

        self.logger.warning(f"步骤重试失败: {step.step_id}, 已重试{max_retries}次")
        return step.result  # 返回最后一次的结果

    def pause_execution(self):
        """暂停执行"""
        if self.current_status == ExecutionStatus.RUNNING:
            self.current_status = ExecutionStatus.PAUSED
            self.logger.info("执行已暂停")

    def resume_execution(self):
        """恢复执行"""
        if self.current_status == ExecutionStatus.PAUSED:
            self.current_status = ExecutionStatus.RUNNING
            self.logger.info("执行已恢复")

    def cancel_execution(self):
        """取消执行"""
        self.stop_requested = True
        if self.current_status in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]:
            self.current_status = ExecutionStatus.CANCELLED
            self.logger.info("执行已取消")

    def get_step_info(self, step_id: str) -> Dict[str, Any]:
        """获取步骤信息

        Args:
            step_id: 步骤ID

        Returns:
            步骤信息字典
        """
        step = self.calibration_steps.get(step_id)
        if not step:
            return {}

        return step.get_summary()

    def get_all_steps_info(self) -> Dict[str, Any]:
        """获取所有步骤信息

        Returns:
            所有步骤信息字典
        """
        return {step_id: step.get_summary() for step_id, step in self.calibration_steps.items()}

    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行状态

        Returns:
            执行状态字典
        """
        status_info = {
            'current_status': self.current_status.value,
            'config': self.config.to_dict(),
            'total_executions': len(self.execution_history),
            'steps_info': self.get_all_steps_info()
        }

        if self.current_execution:
            status_info['current_execution'] = self.current_execution.to_dict()

        return status_info

    def reset_all_steps(self):
        """重置所有步骤状态"""
        for step in self.calibration_steps.values():
            step.reset()

        self.current_status = ExecutionStatus.IDLE
        self.stop_requested = False
        self.logger.info("所有步骤状态已重置")

    def get_execution_statistics(self) -> Dict[str, Any]:
        """获取执行统计信息

        Returns:
            统计信息字典
        """
        if not self.execution_history:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate_percent': 0.0
            }

        successful = len([r for r in self.execution_history if r.status == ExecutionStatus.COMPLETED])
        failed = len([r for r in self.execution_history if r.status == ExecutionStatus.FAILED])

        # 步骤级统计
        step_stats = {}
        for execution in self.execution_history:
            for step_id, result in execution.step_results.items():
                if step_id not in step_stats:
                    step_stats[step_id] = {'total': 0, 'success': 0, 'failed': 0}

                step_stats[step_id]['total'] += 1
                if result.status == StepStatus.SUCCESS:
                    step_stats[step_id]['success'] += 1
                elif result.status == StepStatus.FAILED:
                    step_stats[step_id]['failed'] += 1

        return {
            'total_executions': len(self.execution_history),
            'successful_executions': successful,
            'failed_executions': failed,
            'success_rate_percent': round(successful / len(self.execution_history) * 100, 2),
            'step_statistics': {
                step_id: {
                    **stats,
                    'success_rate_percent': round(stats['success'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0
                }
                for step_id, stats in step_stats.items()
            }
        }


if __name__ == "__main__":
    # 测试校表执行器
    print("=== 校表执行器测试 ===\n")

    # 注意：需要实际的通信器进行完整测试
    try:
        from .device_communicator import DeviceCommunicator
        from .serial_port import SerialPort

        # 创建测试组件 (这里使用模拟对象)
        serial_port = SerialPort()  # 需要实际串口
        communicator = DeviceCommunicator(serial_port)

        # 创建执行配置
        config = ExecutionConfig(
            mode=ExecutionMode.SELECTED_STEPS,
            stop_on_error=False,
            auto_retry_failed=True,
            max_step_retries=1
        )

        # 创建执行器
        executor = CalibrationExecutor(communicator, config)

        # 创建测试参数
        params = CalibrationParameters(
            standard_voltage=220.0,
            standard_current=1.0,
            frequency=50.0
        )

        print("校表执行器已创建")
        print(f"配置: {config.to_dict()}")

        # 获取步骤信息
        steps_info = executor.get_all_steps_info()
        print(f"\n可用步骤数量: {len(steps_info)}")
        for step_id, info in steps_info.items():
            print(f"  {step_id}: {info['name']} (DI: {info['di_code']})")

        print("\n注意: 需要连接实际设备进行完整执行测试")

    except Exception as e:
        print(f"测试初始化失败: {e}")

    print("\n=== 校表执行器测试完成 ===")