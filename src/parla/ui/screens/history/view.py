"""View for learning history screen (SCREEN-C4)."""

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from parla.services.query_models import DailySummary, HistoryOverview
from parla.ui.screens.history.view_model import HistoryViewModel
from parla.ui.widgets.calendar_widget import CalendarWidget
from parla.ui.widgets.wpm_chart import WpmChartWidget


class HistoryView(QWidget):
    """Learning history view with calendar, daily summary, and WPM chart."""

    def __init__(self, view_model: HistoryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Upper section: calendar + daily summary
        upper = QHBoxLayout()

        self._calendar = CalendarWidget()
        upper.addWidget(self._calendar)

        summary_group = QGroupBox("日別サマリー")
        summary_form = QFormLayout(summary_group)
        self._date_label = QLabel("---")
        summary_form.addRow("日付:", self._date_label)
        self._session_count_label = QLabel("---")
        summary_form.addRow("セッション数:", self._session_count_label)
        self._passage_count_label = QLabel("---")
        summary_form.addRow("パッセージ数:", self._passage_count_label)
        self._new_item_label = QLabel("---")
        summary_form.addRow("新規項目:", self._new_item_label)
        self._review_count_label = QLabel("---")
        summary_form.addRow("復習数:", self._review_count_label)
        self._review_accuracy_label = QLabel("---")
        summary_form.addRow("復習正答率:", self._review_accuracy_label)
        self._avg_wpm_label = QLabel("---")
        summary_form.addRow("平均WPM:", self._avg_wpm_label)
        upper.addWidget(summary_group)

        layout.addLayout(upper)

        # Lower section: WPM trend chart
        wpm_group = QGroupBox("WPM推移")
        wpm_layout = QVBoxLayout(wpm_group)
        self._wpm_chart = WpmChartWidget()
        wpm_layout.addWidget(self._wpm_chart)
        layout.addWidget(wpm_group)

    def _connect_signals(self) -> None:
        self._vm.overview_loaded.connect(self._on_overview_loaded)
        self._vm.daily_summary_loaded.connect(self._on_daily_summary_loaded)
        self._calendar.date_selected.connect(self._vm.select_date)

    def _on_overview_loaded(self, overview: HistoryOverview) -> None:
        self._calendar.set_markers(overview.calendar_markers)
        self._wpm_chart.set_data(overview.wpm_trend)

    def _on_daily_summary_loaded(self, summary: DailySummary) -> None:
        self._date_label.setText(str(summary.date))
        self._session_count_label.setText(str(summary.session_count))
        self._passage_count_label.setText(str(summary.passage_count))
        self._new_item_label.setText(str(summary.new_item_count))
        self._review_count_label.setText(str(summary.review_count))

        if summary.review_count > 0:
            accuracy = summary.review_correct_count / summary.review_count * 100
            self._review_accuracy_label.setText(f"{accuracy:.0f}%")
        else:
            self._review_accuracy_label.setText("---")

        self._avg_wpm_label.setText(f"{summary.average_wpm:.0f}" if summary.average_wpm else "---")
