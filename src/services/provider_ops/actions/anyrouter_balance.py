"""
Anyrouter 余额查询操作（含自动签到）
"""

from typing import Any, Dict, Optional, Tuple

import httpx

from src.core.logger import logger
from src.services.provider_ops.actions.balance import BalanceAction
from src.services.provider_ops.types import ActionResult, ActionStatus


class AnyrouterBalanceAction(BalanceAction):
    """
    Anyrouter 专用余额查询

    特点：
    - 查询余额前自动触发签到
    - 签到结果附加到余额信息的 extra 字段
    - Cookie 失效时返回友好的错误提示
    """

    display_name = "查询余额（含自动签到）"
    description = "查询账户余额，同时自动签到"

    def _handle_http_error(
        self, response: httpx.Response, raw_data: Optional[Dict[str, Any]] = None
    ) -> ActionResult:
        """处理 HTTP 错误响应（Anyrouter 专用）"""
        status_code = response.status_code

        # Anyrouter 使用 Cookie 认证，提供更友好的错误提示
        if status_code == 401:
            return self._make_error_result(
                ActionStatus.AUTH_FAILED, "Cookie 已失效，请重新配置", raw_response=raw_data
            )
        elif status_code == 403:
            return self._make_error_result(
                ActionStatus.AUTH_FAILED, "Cookie 已失效或无权限", raw_response=raw_data
            )

        # 其他错误使用基类处理
        return super()._handle_http_error(response, raw_data)

    async def execute(self, client) -> ActionResult:
        """执行余额查询（含自动签到）"""
        # 先尝试签到
        checkin_success, checkin_message = await self._auto_checkin(client)

        # 执行余额查询
        result = await super().execute(client)

        # 将签到结果附加到 extra 字段
        if result.data and hasattr(result.data, "extra"):
            if result.data.extra is None:
                result.data.extra = {}
            result.data.extra["checkin_success"] = checkin_success
            result.data.extra["checkin_message"] = checkin_message

        return result

    async def _auto_checkin(self, client) -> Tuple[Optional[bool], str]:
        """
        自动签到

        Returns:
            (success, message) 元组:
            - success: True=签到成功, False=签到失败, None=已签到/跳过
            - message: 签到消息
        """
        checkin_endpoint = self.config.get("checkin_endpoint", "/api/user/sign_in")

        try:
            response = await client.post(checkin_endpoint)

            if response.status_code == 200:
                try:
                    data = response.json()
                    success = data.get("success", False)
                    message = data.get("message", "")

                    if success:
                        logger.debug(f"Anyrouter 自动签到成功: {message}")
                        return True, message or "签到成功"
                    else:
                        # 检查是否是"已签到"
                        is_already = (
                            any(ind in message for ind in ["已签到", "已签", "今日已"])
                            or "already" in message.lower()
                        )
                        if is_already:
                            logger.debug(f"Anyrouter 今日已签到: {message}")
                            return None, message or "今日已签到"
                        else:
                            logger.debug(f"Anyrouter 签到失败: {message}")
                            return False, message or "签到失败"
                except Exception as e:
                    logger.debug(f"Anyrouter 签到响应解析失败: {e}")
                    return False, "响应解析失败"
            else:
                logger.debug(f"Anyrouter 签到请求失败: HTTP {response.status_code}")
                return False, f"HTTP {response.status_code}"

        except Exception as e:
            logger.debug(f"Anyrouter 自动签到异常: {e}")
            return False, str(e)
