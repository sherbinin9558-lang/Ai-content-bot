"""Бизнес-модель AI Content Bot: тарифы, кредиты и готовые сценарии.

Цены здесь не являются юридическим/финансовым обещанием. Это продуктовая
конфигурация MVP, которую можно менять без изменения ядра генерации.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    key: str
    title: str
    monthly_rub: int | None
    credits: int
    description: str


PLANS: tuple[Plan, ...] = (
    Plan("free", "Free", None, 5, "5 стартовых кредитов для знакомства с ботом."),
    Plan("starter", "Starter", 490, 300, "Для регулярного создания контента."),
    Plan("creator", "Creator", 990, 800, "Для активного автора и небольшого бизнеса."),
    Plan("business", "Business", 2490, 2500, "Для команды и коммерческого контента."),
)


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    feature: str
    description: str


TEMPLATES: tuple[Template, ...] = (
    Template(
        "product_card",
        "Карточка товара",
        "product_card",
        "Название → описание → характеристики → аудитория → готовая продающая карточка.",
    ),
    Template(
        "ad_creative",
        "Рекламный креатив",
        "ad_creative",
        "Продукт → аудитория → площадка → стиль → цель → несколько рекламных концепций.",
    ),
    Template(
        "social_pack",
        "Пакет для соцсетей",
        "social",
        "Одна тема → пост → короткий сценарий → варианты CTA для публикации.",
    ),
    Template(
        "video_script",
        "Сценарий короткого видео",
        "video",
        "Тема → формат → длительность → стиль → площадка → готовая структура ролика.",
    ),
)


def plans_text() -> str:
    lines = ["⭐ Тарифная модель", "", "Free — 5 кредитов · бесплатно"]
    for plan in PLANS[1:]:
        lines.append(f"{plan.title} — {plan.credits} кредитов · {plan.monthly_rub} ₽/мес.")
    lines += [
        "",
        "Модель монетизации:",
        "• бесплатный вход;",
        "• подписка с месячным пакетом кредитов;",
        "• докупка кредитов;",
        "• расход зависит от выбранной AI-модели.",
        "",
        "Цены — конфигурация MVP и не считаются финальным коммерческим прайсом.",
    ]
    return "\n".join(lines)


def templates_text() -> str:
    lines = ["🧩 Готовые сценарии", ""]
    for item in TEMPLATES:
        lines.append(f"• {item.title} — {item.description}")
    lines += [
        "",
        "Пользователь по-прежнему сам выбирает провайдера и конкретную модель.",
        "Шаблон меняет сценарий задачи, а не скрывает выбор AI.",
    ]
    return "\n".join(lines)
