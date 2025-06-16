"""
告警系统

提供多渠道告警通知功能，支持邮件、Slack、日志等方式。
用于双策略迁移过程中的实时告警通知。
"""

import logging
import smtplib
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from ..migration.health_monitor import HealthAlert


@dataclass
class AlertConfig:
    """告警配置"""
    # 邮件告警配置
    enable_email_alerts: bool = False
    smtp_server: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = "pktmask@company.com"
    email_recipients: List[str] = field(default_factory=list)
    
    # Slack告警配置
    enable_slack_alerts: bool = False
    slack_webhook_url: str = ""
    slack_channel: str = "#pktmask-alerts"
    
    # 日志告警配置
    enable_log_alerts: bool = True
    alert_log_file: str = "/var/log/pktmask/alerts.log"
    
    # 告警抑制配置
    alert_cooldown_minutes: int = 15
    max_alerts_per_hour: int = 10
    
    # 告警升级配置
    enable_escalation: bool = False
    escalation_timeout_minutes: int = 30
    escalation_contacts: List[str] = field(default_factory=list)


@dataclass
class AlertRecord:
    """告警记录"""
    alert: HealthAlert
    sent_time: datetime
    channels: List[str]  # 发送渠道
    success: bool
    error_message: Optional[str] = None


class AlertSystem:
    """告警系统"""
    
    def __init__(self, config: AlertConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 告警历史记录
        self.alert_history: List[AlertRecord] = []
        
        # 告警抑制记录
        self.suppression_cache: Dict[str, datetime] = {}
        
        # 告警计数器
        self.hourly_alert_count = 0
        self.last_hour_reset = datetime.now()
        
        # 自定义告警处理器
        self.custom_handlers: List[Callable[[HealthAlert], None]] = []
        
        # 初始化告警日志
        if self.config.enable_log_alerts:
            self._setup_alert_logging()
    
    def _setup_alert_logging(self):
        """设置告警日志"""
        alert_logger = logging.getLogger('pktmask.alerts')
        alert_logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.config.alert_log_file)
        file_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        alert_logger.addHandler(file_handler)
        self.alert_logger = alert_logger
    
    def register_custom_handler(self, handler: Callable[[HealthAlert], None]):
        """注册自定义告警处理器"""
        self.custom_handlers.append(handler)
    
    def send_alert(self, alert: HealthAlert) -> bool:
        """发送告警"""
        try:
            # 检查告警抑制
            if self._is_alert_suppressed(alert):
                self.logger.debug(f"告警被抑制: {alert.message}")
                return True
            
            # 检查告警频率限制
            if not self._check_rate_limit():
                self.logger.warning("告警频率超限，跳过发送")
                return False
            
            # 发送告警到各个渠道
            channels_used = []
            success = True
            error_message = None
            
            try:
                # 邮件告警
                if self.config.enable_email_alerts:
                    email_success = self._send_email_alert(alert)
                    if email_success:
                        channels_used.append("email")
                    else:
                        success = False
                
                # Slack告警
                if self.config.enable_slack_alerts:
                    slack_success = self._send_slack_alert(alert)
                    if slack_success:
                        channels_used.append("slack")
                    else:
                        success = False
                
                # 日志告警
                if self.config.enable_log_alerts:
                    self._send_log_alert(alert)
                    channels_used.append("log")
                
                # 自定义处理器
                for handler in self.custom_handlers:
                    try:
                        handler(alert)
                        channels_used.append("custom")
                    except Exception as e:
                        self.logger.error(f"自定义告警处理器失败: {e}")
                        success = False
                
            except Exception as e:
                success = False
                error_message = str(e)
                self.logger.error(f"告警发送失败: {e}")
            
            # 记录告警
            alert_record = AlertRecord(
                alert=alert,
                sent_time=datetime.now(),
                channels=channels_used,
                success=success,
                error_message=error_message
            )
            self.alert_history.append(alert_record)
            
            # 更新抑制缓存
            self._update_suppression_cache(alert)
            
            # 更新计数器
            self._update_rate_limit_counter()
            
            return success
            
        except Exception as e:
            self.logger.error(f"告警系统异常: {e}")
            return False
    
    def _is_alert_suppressed(self, alert: HealthAlert) -> bool:
        """检查告警是否被抑制"""
        alert_key = f"{alert.severity}_{hash(alert.message)}"
        
        if alert_key in self.suppression_cache:
            last_sent = self.suppression_cache[alert_key]
            cooldown_time = timedelta(minutes=self.config.alert_cooldown_minutes)
            
            if datetime.now() - last_sent < cooldown_time:
                return True
        
        return False
    
    def _update_suppression_cache(self, alert: HealthAlert):
        """更新告警抑制缓存"""
        alert_key = f"{alert.severity}_{hash(alert.message)}"
        self.suppression_cache[alert_key] = datetime.now()
        
        # 清理过期的抑制记录
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.suppression_cache = {
            k: v for k, v in self.suppression_cache.items()
            if v > cutoff_time
        }
    
    def _check_rate_limit(self) -> bool:
        """检查告警频率限制"""
        current_time = datetime.now()
        
        # 重置每小时计数器
        if current_time - self.last_hour_reset >= timedelta(hours=1):
            self.hourly_alert_count = 0
            self.last_hour_reset = current_time
        
        return self.hourly_alert_count < self.config.max_alerts_per_hour
    
    def _update_rate_limit_counter(self):
        """更新频率限制计数器"""
        self.hourly_alert_count += 1
    
    def _send_email_alert(self, alert: HealthAlert) -> bool:
        """发送邮件告警"""
        try:
            if not self.config.email_recipients:
                return True  # 没有配置收件人，认为成功
            
            # 创建邮件内容
            subject = f"[PktMask Alert] {alert.severity} - {alert.message}"
            
            body = self._format_email_body(alert)
            
            # 创建邮件消息
            msg = MimeMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(self.config.email_recipients)
            msg['Subject'] = subject
            
            msg.attach(MimeText(body, 'html'))
            
            # 发送邮件
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.starttls()
            
            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)
            
            text = msg.as_string()
            server.sendmail(
                self.config.email_from,
                self.config.email_recipients,
                text
            )
            server.quit()
            
            self.logger.info(f"邮件告警发送成功: {alert.message}")
            return True
            
        except Exception as e:
            self.logger.error(f"邮件告警发送失败: {e}")
            return False
    
    def _format_email_body(self, alert: HealthAlert) -> str:
        """格式化邮件正文"""
        return f"""
        <html>
        <head></head>
        <body>
            <h2 style="color: {'red' if alert.severity == 'CRITICAL' else 'orange'};">
                PktMask 系统告警
            </h2>
            
            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">严重程度</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.severity}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">告警消息</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.message}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">时间</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{alert.timestamp}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">建议措施</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">
                        <ul>
                            {''.join(f'<li>{action}</li>' for action in alert.recommended_actions)}
                        </ul>
                    </td>
                </tr>
            </table>
            
            <h3>详细指标</h3>
            <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">
{json.dumps(alert.metrics, indent=2, ensure_ascii=False)}
            </pre>
            
            <p style="color: #666; font-size: 12px;">
                此邮件由PktMask双策略监控系统自动发送。如有疑问，请联系运维团队。
            </p>
        </body>
        </html>
        """
    
    def _send_slack_alert(self, alert: HealthAlert) -> bool:
        """发送Slack告警"""
        try:
            if not self.config.slack_webhook_url:
                return True  # 没有配置Webhook，认为成功
            
            # 确定颜色
            color_map = {
                'CRITICAL': '#FF0000',
                'HIGH': '#FF6600',
                'MEDIUM': '#FFAA00',
                'LOW': '#00AA00'
            }
            color = color_map.get(alert.severity, '#666666')
            
            # 构造Slack消息
            payload = {
                "channel": self.config.slack_channel,
                "username": "PktMask Monitor",
                "icon_emoji": ":warning:",
                "attachments": [{
                    "color": color,
                    "title": f"{alert.severity} Alert - PktMask",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "时间",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        },
                        {
                            "title": "严重程度",
                            "value": alert.severity,
                            "short": True
                        }
                    ],
                    "footer": "PktMask Monitoring System",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            # 添加建议措施
            if alert.recommended_actions:
                payload["attachments"][0]["fields"].append({
                    "title": "建议措施",
                    "value": "\n".join(f"• {action}" for action in alert.recommended_actions),
                    "short": False
                })
            
            # 发送请求
            response = requests.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info(f"Slack告警发送成功: {alert.message}")
                return True
            else:
                self.logger.error(f"Slack告警发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Slack告警发送失败: {e}")
            return False
    
    def _send_log_alert(self, alert: HealthAlert):
        """发送日志告警"""
        try:
            alert_data = {
                'severity': alert.severity,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'metrics': alert.metrics,
                'recommended_actions': alert.recommended_actions,
                'acknowledged': alert.acknowledged
            }
            
            self.alert_logger.info(json.dumps(alert_data, ensure_ascii=False))
            
        except Exception as e:
            self.logger.error(f"日志告警记录失败: {e}")
    
    def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取告警统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            record for record in self.alert_history
            if record.sent_time > cutoff_time
        ]
        
        if not recent_alerts:
            return {
                'total_alerts': 0,
                'by_severity': {},
                'by_channel': {},
                'success_rate': 1.0
            }
        
        # 按严重程度统计
        by_severity = {}
        for record in recent_alerts:
            severity = record.alert.severity
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # 按渠道统计
        by_channel = {}
        for record in recent_alerts:
            for channel in record.channels:
                by_channel[channel] = by_channel.get(channel, 0) + 1
        
        # 成功率统计
        successful_alerts = sum(1 for record in recent_alerts if record.success)
        success_rate = successful_alerts / len(recent_alerts) if recent_alerts else 1.0
        
        return {
            'total_alerts': len(recent_alerts),
            'by_severity': by_severity,
            'by_channel': by_channel,
            'success_rate': success_rate,
            'period_hours': hours
        }
    
    def clear_suppression_cache(self):
        """清空告警抑制缓存"""
        self.suppression_cache.clear()
        self.logger.info("告警抑制缓存已清空")
    
    def test_alert_channels(self) -> Dict[str, bool]:
        """测试告警渠道"""
        test_alert = HealthAlert(
            severity="LOW",
            message="告警系统测试消息",
            recommended_actions=["这是一个测试告警，无需处理"]
        )
        
        results = {}
        
        # 测试邮件
        if self.config.enable_email_alerts:
            results['email'] = self._send_email_alert(test_alert)
        
        # 测试Slack
        if self.config.enable_slack_alerts:
            results['slack'] = self._send_slack_alert(test_alert)
        
        # 测试日志
        if self.config.enable_log_alerts:
            try:
                self._send_log_alert(test_alert)
                results['log'] = True
            except Exception:
                results['log'] = False
        
        return results 