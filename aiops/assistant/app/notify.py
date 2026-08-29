"""notify.py — 告警多渠道通知（钉钉 / 企业微信 / 邮件）

在 AIOps 分析完成后调用，把「原始告警 + AI 诊断」推送到各渠道。
每个渠道用环境变量控制开关，未配置则自动跳过。

环境变量:
  钉钉:   DINGTALK_WEBHOOK (https://oapi.dingtalk.com/robot/send?access_token=xxx)
  企业微信: WECOM_WEBHOOK (https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx)
  邮件:   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_TO (逗号分隔多个收件人)
"""
import os
import smtplib
import json
import urllib.request
from email.mime.text import MIMEText
from email.header import Header


def _post_json(url: str, payload: dict) -> str:
    """发送 JSON POST 请求，返回响应文本。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa
        return f"[notify失败] {e}"


# ---------- 钉钉 ----------
def notify_dingtalk(title: str, text: str) -> str:
    url = os.getenv("DINGTALK_WEBHOOK", "")
    if not url:
        return "[钉钉未配置]"
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }
    return _post_json(url, payload)


# ---------- 企业微信 ----------
def notify_wecom(title: str, text: str) -> str:
    url = os.getenv("WECOM_WEBHOOK", "")
    if not url:
        return "[企业微信未配置]"
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"**【{title}】**\n{text}"},
    }
    return _post_json(url, payload)


# ---------- 邮件 ----------
def notify_email(title: str, text: str) -> str:
    host = os.getenv("SMTP_HOST", "")
    if not host:
        return "[邮件未配置]"
    try:
        port = int(os.getenv("SMTP_PORT", "465") or "465")
    except ValueError:
        port = 465
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    to = os.getenv("MAIL_TO", "")
    if not (user and pwd and to):
        return "[邮件配置不完整]"
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = user
    msg["To"] = to
    try:
        if port == 465:
            s = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            s = smtplib.SMTP(host, port, timeout=10)
            s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
        s.quit()
        return "[邮件已发送]"
    except Exception as e:  # noqa
        return f"[邮件失败] {e}"


# ---------- 统一入口 ----------
def notify_all(alert_name: str, summary: str, diagnosis: str):
    """把告警 + AI 诊断推送到所有已配置的渠道。"""
    title = f"[AIOps] 告警 {alert_name}"
    text = (
        f"**告警**: {alert_name}\n"
        f"**摘要**: {summary}\n"
        f"**AI 根因分析**:\n{diagnosis}"
    )
    results = {
        "dingtalk": notify_dingtalk(title, text),
        "wecom": notify_wecom(alert_name, text),
        "email": notify_email(title, text),
    }
    # 打印到日志便于查看
    print(f"[notify] {json.dumps(results, ensure_ascii=False)}", flush=True)
    return results


# ---------- 故障恢复通知 ----------
def notify_resolved(alert_name: str, summary: str = "", resolved_at: str = ""):
    """告警恢复时通知：告知故障已解除。"""
    title = f"[AIOps] ✅ 告警已恢复 {alert_name}"
    text = (
        f"**告警**: {alert_name}\n"
        f"**状态**: 已恢复 (resolved)\n"
        f"**摘要**: {summary if summary else '告警已解除'}\n"
        f"**恢复时间**: {resolved_at if resolved_at else '见告警详情'}\n\n"
        f"故障已解除，无需处理。"
    )
    results = {
        "dingtalk": notify_dingtalk(title, text),
        "wecom": notify_wecom(alert_name, text),
        "email": notify_email(title, text),
    }
    print(f"[notify-resolved] {json.dumps(results, ensure_ascii=False)}", flush=True)
    return results
