"""
Skill MQTT_SEND — publier sur un topic MQTT.
"""
DESCRIPTION = "Publier un message sur un topic MQTT (communication inter-agents)"
USAGE = "SKILL:mqtt_send ARGS:<topic> | <message>"


def run(args: str, context) -> str:
    if "|" not in args:
        return "Format : SKILL:mqtt_send ARGS:<topic> | <message>"
    topic, message = args.split("|", 1)
    context.mqtt.publish_raw(topic.strip(), message.strip())
    return f"Message publié sur '{topic.strip()}'."
