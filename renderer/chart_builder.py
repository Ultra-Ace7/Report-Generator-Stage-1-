"""Render portable PNG chart bytes without GUI state or report calculations."""
from datetime import date
from io import BytesIO
import textwrap

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, DateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from reports.base import ChartSpec


def render_chart(spec: ChartSpec) -> bytes:
    figure = Figure(figsize=(8.4, 4.8), dpi=160, facecolor="white")
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    figure.subplots_adjust(left=0.13, right=0.97, top=0.85, bottom=0.25)
    values = [float(value) for value in spec.values]
    if spec.kind == "sales_trend":
        dates = [date.fromisoformat(label) for label in spec.labels]
        axis.plot(dates, values, color="#146C94", linewidth=2, marker="o", markersize=6)
        locator = AutoDateLocator(minticks=3, maxticks=7)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(ConciseDateFormatter(locator))
        if len(dates) <= 7:
            axis.set_xticks(dates)
            axis.xaxis.set_major_formatter(DateFormatter("%d %b\n%Y"))
        axis.set_xlabel("Recorded order date", labelpad=9)
        axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        axis.margins(x=0.08)
    else:
        bars = axis.bar(spec.labels, values, color=["#167D8D", "#E5A23B"], width=0.52)
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        for bar, value in zip(bars, values):
            axis.annotate("{:.0f}".format(value), (bar.get_x() + bar.get_width() / 2, value),
                          xytext=(0, 7), textcoords="offset points", ha="center", fontsize=11)
    axis.set_ylim(0, max(max(values) * 1.2, 1))
    axis.set_title(spec.title, loc="left", fontsize=15, fontweight="bold", color="#163D52", pad=18)
    axis.set_ylabel(spec.y_label, labelpad=10)
    axis.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    axis.set_axisbelow(True)
    for edge in ("top", "right"):
        axis.spines[edge].set_visible(False)
    for edge in ("bottom", "left"):
        axis.spines[edge].set_color("#CBD5E1")
    figure.text(0.13, 0.055, "\n".join(textwrap.wrap(spec.caption, 100)), fontsize=8, color="#475569", va="bottom")
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=160)
    return buffer.getvalue()
