#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话记录器 - M4阶段
轻量级的校表会话记录系统，基于JSON文件存储
无数据库依赖，支持会话导出和简单统计
"""

import json
import os
import csv
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
import logging
from enum import Enum


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"              # 活跃中
    COMPLETED = "completed"        # 已完成
    INTERRUPTED = "interrupted"    # 中断
    FAILED = "failed"             # 失败


@dataclass
class StepRecord:
    """步骤记录"""
    step_id: str                   # 步骤ID
    step_name: str                 # 步骤名称
    di_code: str                   # DI码
    start_time: str               # 开始时间
    end_time: Optional[str] = None # 结束时间
    status: str = "pending"        # 状态
    correction_value: Optional[float] = None  # 校正值
    execution_time: Optional[float] = None    # 执行时间(秒)
    error_message: Optional[str] = None       # 错误信息
    parameters: Optional[Dict] = None         # 执行参数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class CalibrationSession:
    """校表会话"""
    session_id: str                # 会话ID
    start_time: str               # 开始时间
    end_time: Optional[str] = None # 结束时间
    status: SessionStatus = SessionStatus.ACTIVE  # 会话状态

    # 配置信息
    serial_config: Optional[Dict] = None      # 串口配置
    standard_values: Optional[Dict] = None    # 标准值
    device_info: Optional[Dict] = None        # 设备信息

    # 执行记录
    steps: List[StepRecord] = None            # 步骤记录
    total_steps: int = 0                      # 总步骤数
    successful_steps: int = 0                 # 成功步骤数
    failed_steps: int = 0                     # 失败步骤数

    # 统计信息
    total_duration: Optional[float] = None    # 总耗时(秒)
    success_rate: float = 0.0                # 成功率
    notes: Optional[str] = None               # 备注信息

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data


class SessionRecorder:
    """会话记录器

    特性:
    - JSON文件存储，无数据库依赖
    - 按会话组织记录
    - 简单统计分析
    - 多格式导出支持
    """

    def __init__(self, records_dir: str = "records"):
        """初始化会话记录器

        Args:
            records_dir: 记录文件目录
        """
        self.records_dir = Path(records_dir)
        self.records_dir.mkdir(exist_ok=True)

        # 按年月组织记录
        self.current_month_dir = self.records_dir / datetime.now().strftime("%Y-%m")
        self.current_month_dir.mkdir(exist_ok=True)

        self.logger = logging.getLogger("SessionRecorder")

        # 当前活跃会话
        self.current_session: Optional[CalibrationSession] = None

    def start_session(self, session_config: Optional[Dict] = None) -> str:
        """开始新的校表会话

        Args:
            session_config: 会话配置信息

        Returns:
            会话ID
        """
        # 结束之前的会话（如果有）
        if self.current_session and self.current_session.status == SessionStatus.ACTIVE:
            self.logger.warning("发现未结束的会话，自动结束")
            self.end_session("interrupted")

        # 创建新会话
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"

        self.current_session = CalibrationSession(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            status=SessionStatus.ACTIVE
        )

        # 设置会话配置
        if session_config:
            self.current_session.serial_config = session_config.get('serial_config')
            self.current_session.standard_values = session_config.get('standard_values')
            self.current_session.device_info = session_config.get('device_info')

        self.logger.info(f"开始校表会话: {session_id}")
        return session_id

    def record_step_result(self, step_id: str, step_name: str, di_code: str,
                          status: str, correction_value: Optional[float] = None,
                          execution_time: Optional[float] = None,
                          error_message: Optional[str] = None,
                          parameters: Optional[Dict] = None):
        """记录步骤结果

        Args:
            step_id: 步骤ID
            step_name: 步骤名称
            di_code: DI码
            status: 执行状态 (success/failed/skipped)
            correction_value: 校正值
            execution_time: 执行时间
            error_message: 错误信息
            parameters: 执行参数
        """
        if not self.current_session:
            self.logger.error("没有活跃的校表会话")
            return

        # 查找是否已有该步骤记录
        existing_step = None
        for step in self.current_session.steps:
            if step.step_id == step_id:
                existing_step = step
                break

        if existing_step:
            # 更新现有记录
            existing_step.end_time = datetime.now().isoformat()
            existing_step.status = status
            existing_step.correction_value = correction_value
            existing_step.execution_time = execution_time
            existing_step.error_message = error_message
            if parameters:
                existing_step.parameters = parameters
        else:
            # 创建新的步骤记录
            step_record = StepRecord(
                step_id=step_id,
                step_name=step_name,
                di_code=di_code,
                start_time=datetime.now().isoformat(),
                end_time=datetime.now().isoformat(),
                status=status,
                correction_value=correction_value,
                execution_time=execution_time,
                error_message=error_message,
                parameters=parameters
            )
            self.current_session.steps.append(step_record)

        # 更新会话统计
        self._update_session_statistics()

        self.logger.debug(f"记录步骤结果: {step_id} - {status}")

    def add_session_note(self, note: str):
        """添加会话备注

        Args:
            note: 备注内容
        """
        if not self.current_session:
            self.logger.error("没有活跃的校表会话")
            return

        if self.current_session.notes:
            self.current_session.notes += f"\n{note}"
        else:
            self.current_session.notes = note

    def end_session(self, final_status: str = "completed", summary: Optional[str] = None) -> bool:
        """结束当前会话

        Args:
            final_status: 最终状态 (completed/interrupted/failed)
            summary: 会话总结

        Returns:
            是否成功结束
        """
        if not self.current_session:
            self.logger.warning("没有活跃的校表会话可以结束")
            return False

        try:
            # 设置结束时间和状态
            self.current_session.end_time = datetime.now().isoformat()

            if final_status == "completed":
                self.current_session.status = SessionStatus.COMPLETED
            elif final_status == "interrupted":
                self.current_session.status = SessionStatus.INTERRUPTED
            elif final_status == "failed":
                self.current_session.status = SessionStatus.FAILED
            else:
                self.current_session.status = SessionStatus.COMPLETED

            # 添加总结
            if summary:
                self.add_session_note(f"会话总结: {summary}")

            # 计算总耗时
            start_time = datetime.fromisoformat(self.current_session.start_time)
            end_time = datetime.fromisoformat(self.current_session.end_time)
            self.current_session.total_duration = (end_time - start_time).total_seconds()

            # 更新统计信息
            self._update_session_statistics()

            # 保存会话记录
            success = self._save_session()

            if success:
                self.logger.info(f"会话结束: {self.current_session.session_id} ({final_status})")
                self.current_session = None
                return True
            else:
                self.logger.error("会话保存失败")
                return False

        except Exception as e:
            self.logger.error(f"结束会话异常: {e}")
            return False

    def _update_session_statistics(self):
        """更新会话统计信息"""
        if not self.current_session:
            return

        self.current_session.total_steps = len(self.current_session.steps)
        self.current_session.successful_steps = len([
            step for step in self.current_session.steps if step.status == "success"
        ])
        self.current_session.failed_steps = len([
            step for step in self.current_session.steps if step.status == "failed"
        ])

        if self.current_session.total_steps > 0:
            self.current_session.success_rate = (
                self.current_session.successful_steps / self.current_session.total_steps * 100
            )

    def _save_session(self) -> bool:
        """保存会话记录到文件"""
        if not self.current_session:
            return False

        try:
            session_file = self.current_month_dir / f"{self.current_session.session_id}.json"

            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_session.to_dict(), f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            self.logger.error(f"保存会话记录失败: {e}")
            return False

    def load_session(self, session_id: str) -> Optional[CalibrationSession]:
        """加载指定会话记录

        Args:
            session_id: 会话ID

        Returns:
            会话对象或None
        """
        try:
            # 在当前月份目录查找
            session_file = self.current_month_dir / f"{session_id}.json"

            if not session_file.exists():
                # 在所有月份目录查找
                for month_dir in self.records_dir.glob("????-??"):
                    session_file = month_dir / f"{session_id}.json"
                    if session_file.exists():
                        break
                else:
                    return None

            with open(session_file, 'r', encoding='utf-8') as f:
                session_dict = json.load(f)

            # 重构会话对象
            session = CalibrationSession(**{
                k: v for k, v in session_dict.items()
                if k not in ['status', 'steps']
            })
            session.status = SessionStatus(session_dict['status'])

            # 重构步骤记录
            session.steps = [
                StepRecord(**step_dict) for step_dict in session_dict.get('steps', [])
            ]

            return session

        except Exception as e:
            self.logger.error(f"加载会话记录失败: {e}")
            return None

    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的会话列表

        Args:
            limit: 返回数量限制

        Returns:
            会话摘要列表
        """
        sessions = []

        try:
            # 收集所有会话文件
            session_files = []
            for month_dir in sorted(self.records_dir.glob("????-??"), reverse=True):
                for session_file in sorted(month_dir.glob("session_*.json"), reverse=True):
                    session_files.append(session_file)

            # 加载会话摘要
            for session_file in session_files[:limit]:
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_dict = json.load(f)

                    sessions.append({
                        'session_id': session_dict['session_id'],
                        'start_time': session_dict['start_time'],
                        'end_time': session_dict.get('end_time'),
                        'status': session_dict['status'],
                        'total_steps': session_dict.get('total_steps', 0),
                        'successful_steps': session_dict.get('successful_steps', 0),
                        'success_rate': session_dict.get('success_rate', 0.0),
                        'total_duration': session_dict.get('total_duration')
                    })

                except Exception as e:
                    self.logger.warning(f"读取会话文件失败 {session_file}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"获取会话列表失败: {e}")

        return sessions

    def export_session_report(self, session_id: str, format: str = "txt") -> Optional[str]:
        """导出会话报告

        Args:
            session_id: 会话ID
            format: 导出格式 (txt/csv/json)

        Returns:
            导出文件路径或None
        """
        session = self.load_session(session_id)
        if not session:
            self.logger.error(f"会话不存在: {session_id}")
            return None

        try:
            export_dir = self.records_dir / "exports"
            export_dir.mkdir(exist_ok=True)

            if format.lower() == "txt":
                return self._export_to_text(session, export_dir)
            elif format.lower() == "csv":
                return self._export_to_csv(session, export_dir)
            elif format.lower() == "json":
                return self._export_to_json(session, export_dir)
            else:
                self.logger.error(f"不支持的导出格式: {format}")
                return None

        except Exception as e:
            self.logger.error(f"导出会话报告失败: {e}")
            return None

    def _export_to_text(self, session: CalibrationSession, export_dir: Path) -> str:
        """导出为文本格式"""
        export_file = export_dir / f"{session.session_id}_report.txt"

        with open(export_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("电表校准会话报告\n")
            f.write("=" * 60 + "\n\n")

            # 会话信息
            f.write("会话信息:\n")
            f.write(f"  会话ID: {session.session_id}\n")
            f.write(f"  开始时间: {session.start_time}\n")
            f.write(f"  结束时间: {session.end_time or '未结束'}\n")
            f.write(f"  状态: {session.status.value}\n")
            f.write(f"  总耗时: {session.total_duration:.2f}秒\n" if session.total_duration else "  总耗时: 未知\n")
            f.write(f"  成功率: {session.success_rate:.1f}%\n\n")

            # 配置信息
            if session.serial_config:
                f.write("串口配置:\n")
                for key, value in session.serial_config.items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")

            if session.standard_values:
                f.write("标准值配置:\n")
                for key, value in session.standard_values.items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")

            # 步骤详情
            f.write("步骤执行详情:\n")
            f.write("-" * 60 + "\n")
            for i, step in enumerate(session.steps, 1):
                f.write(f"{i}. {step.step_name} ({step.step_id})\n")
                f.write(f"   DI码: {step.di_code}\n")
                f.write(f"   状态: {step.status}\n")
                f.write(f"   执行时间: {step.execution_time:.2f}秒\n" if step.execution_time else "   执行时间: 未知\n")
                if step.correction_value is not None:
                    f.write(f"   校正值: {step.correction_value:+.2f}%\n")
                if step.error_message:
                    f.write(f"   错误信息: {step.error_message}\n")
                f.write("\n")

            # 备注
            if session.notes:
                f.write("备注信息:\n")
                f.write(session.notes)
                f.write("\n\n")

            f.write("=" * 60 + "\n")
            f.write(f"报告生成时间: {datetime.now().isoformat()}\n")

        return str(export_file)

    def _export_to_csv(self, session: CalibrationSession, export_dir: Path) -> str:
        """导出为CSV格式"""
        export_file = export_dir / f"{session.session_id}_steps.csv"

        with open(export_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # CSV标题行
            writer.writerow([
                '步骤ID', '步骤名称', 'DI码', '开始时间', '结束时间',
                '状态', '校正值', '执行时间(秒)', '错误信息'
            ])

            # 步骤数据
            for step in session.steps:
                writer.writerow([
                    step.step_id,
                    step.step_name,
                    step.di_code,
                    step.start_time,
                    step.end_time or '',
                    step.status,
                    step.correction_value or '',
                    step.execution_time or '',
                    step.error_message or ''
                ])

        return str(export_file)

    def _export_to_json(self, session: CalibrationSession, export_dir: Path) -> str:
        """导出为JSON格式"""
        export_file = export_dir / f"{session.session_id}_data.json"

        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

        return str(export_file)

    def get_statistics(self, date_range: Optional[tuple] = None) -> Dict[str, Any]:
        """获取统计信息

        Args:
            date_range: 日期范围 (start_date, end_date)

        Returns:
            统计信息字典
        """
        try:
            sessions = self.get_recent_sessions(limit=100)  # 获取更多数据进行统计

            # 过滤日期范围
            if date_range:
                start_date, end_date = date_range
                filtered_sessions = []
                for session in sessions:
                    session_date = datetime.fromisoformat(session['start_time']).date()
                    if start_date <= session_date <= end_date:
                        filtered_sessions.append(session)
                sessions = filtered_sessions

            if not sessions:
                return {
                    'total_sessions': 0,
                    'completed_sessions': 0,
                    'average_success_rate': 0.0,
                    'total_steps': 0,
                    'successful_steps': 0
                }

            completed_sessions = [s for s in sessions if s['status'] == 'completed']
            total_steps = sum(s['total_steps'] for s in sessions)
            successful_steps = sum(s['successful_steps'] for s in sessions)

            return {
                'total_sessions': len(sessions),
                'completed_sessions': len(completed_sessions),
                'completion_rate': len(completed_sessions) / len(sessions) * 100 if sessions else 0,
                'average_success_rate': sum(s['success_rate'] for s in sessions) / len(sessions) if sessions else 0,
                'total_steps': total_steps,
                'successful_steps': successful_steps,
                'step_success_rate': successful_steps / total_steps * 100 if total_steps > 0 else 0
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}


if __name__ == "__main__":
    # 测试会话记录器
    print("=== 会话记录器测试 ===\n")

    # 创建记录器
    recorder = SessionRecorder("test_records")

    # 开始会话
    session_id = recorder.start_session({
        'serial_config': {'port': 'COM1', 'baudrate': 9600},
        'standard_values': {'voltage': 220.0, 'current': 1.0}
    })
    print(f"开始会话: {session_id}")

    # 模拟步骤执行
    recorder.record_step_result("step1", "电流有效值offset校正", "00F81500",
                              "success", correction_value=1.23, execution_time=2.5)

    recorder.record_step_result("step2", "电压电流增益校正", "00F81600",
                              "failed", error_message="设备无响应", execution_time=3.0)

    recorder.add_session_note("测试会话，仅用于验证功能")

    # 结束会话
    success = recorder.end_session("completed", "测试完成")
    print(f"结束会话: {'成功' if success else '失败'}")

    # 获取会话列表
    recent_sessions = recorder.get_recent_sessions(5)
    print(f"\n最近会话数量: {len(recent_sessions)}")
    for session in recent_sessions:
        print(f"  - {session['session_id']}: {session['status']} (成功率: {session['success_rate']:.1f}%)")

    # 导出报告
    if recent_sessions:
        latest_session_id = recent_sessions[0]['session_id']
        report_file = recorder.export_session_report(latest_session_id, "txt")
        if report_file:
            print(f"\n报告已导出: {report_file}")

    # 获取统计信息
    stats = recorder.get_statistics()
    print(f"\n统计信息:")
    print(f"  总会话数: {stats.get('total_sessions', 0)}")
    print(f"  完成会话数: {stats.get('completed_sessions', 0)}")
    print(f"  平均成功率: {stats.get('average_success_rate', 0):.1f}%")

    print("\n=== 会话记录器测试完成 ===")