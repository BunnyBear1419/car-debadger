import os
import sys
import json
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from PySide6.QtCore import Qt, QThread, Signal, QStandardPaths
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QTextEdit, QTabWidget, QFrame, QMessageBox,
    QCheckBox, QDialog, QFormLayout, QDialogButtonBox, QComboBox, QSplitter
)

APP_NAME = "FiveM Vehicle Debadger"
VEHICLE_EXTS = {".yft", ".ytd"}
TEXTURE_EXTS = {".png", ".tga", ".dds", ".jpg", ".jpeg", ".webp"}
META_NAMES = {"vehicles.meta", "handling.meta", "carvariations.meta", "carcols.meta"}
MANIFEST_NAMES = {"fxmanifest.lua", "__resource.lua"}

def now_tag():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def readable_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{n} B"

@dataclass
class AssetRecord:
    path: str
    relative_path: str
    resource: str
    kind: str
    size: int
    sha256: str
    review: str

def classify_asset(path: Path, root: Path):
    ext = path.suffix.lower()
    name = path.name.lower()
    if ext == ".yft":
        kind = "3D model"
        review = "3D inspection required; badge may be a separate mesh or merged geometry"
    elif ext == ".ytd":
        kind = "Texture dictionary"
        review = "Inspect textures; use compatible YTD export/import workflow"
    elif ext in TEXTURE_EXTS:
        kind = "Image texture"
        review = "Review texture for logos before editing"
    elif name in META_NAMES:
        kind = "Vehicle metadata"
        review = "Preserve unless a specific change is required"
    elif name in MANIFEST_NAMES:
        kind = "Resource manifest"
        review = "Preserve resource structure"
    else:
        kind = "Other"
        review = "Not a debadging target"
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    parts = Path(rel).parts
    resource = parts[0] if len(parts) > 1 else path.parent.name
    return AssetRecord(
        path=str(path), relative_path=rel, resource=resource, kind=kind,
        size=path.stat().st_size, sha256=sha256_file(path), review=review
    )

class ScanWorker(QThread):
    progress = Signal(int, str)
    finished_records = Signal(object)
    failed = Signal(str)

    def __init__(self, root):
        super().__init__()
        self.root = Path(root)

    def run(self):
        try:
            records = []
            paths = [p for p in self.root.rglob("*") if p.is_file()]
            total = max(1, len(paths))
            for i, p in enumerate(paths, 1):
                if p.suffix.lower() in VEHICLE_EXTS or p.suffix.lower() in TEXTURE_EXTS or p.name.lower() in META_NAMES | MANIFEST_NAMES:
                    try:
                        records.append(classify_asset(p, self.root))
                    except (OSError, PermissionError) as e:
                        continue
                if i % 25 == 0 or i == total:
                    self.progress.emit(int(i * 100 / total), f"Scanning {i:,} / {len(paths):,} files…")
            self.finished_records.emit(records)
        except Exception as e:
            self.failed.emit(str(e))

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pipeline Settings")
        self.resize(650, 260)
        self.config = dict(config)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.texture_cmd = QLineEdit(self.config.get("external_texture_command", ""))
        self.model_cmd = QLineEdit(self.config.get("external_model_command", ""))
        self.texture_cmd.setPlaceholderText("Leave blank unless a tested CLI tool is installed")
        self.model_cmd.setPlaceholderText("Leave blank unless a tested CLI tool is installed")
        form.addRow("Texture command:", self.texture_cmd)
        form.addRow("Model command:", self.model_cmd)
        layout.addLayout(form)
        note = QLabel("Commands are optional and are not run unless enabled from a job action. Tokens: {input}, {output}, {workspace}. Confirm your tool's command-line syntax first.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a9b4c4;")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        self.config["external_texture_command"] = self.texture_cmd.text().strip()
        self.config["external_model_command"] = self.model_cmd.text().strip()
        return self.config

class DebadgerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)
        self.setMinimumSize(1050, 700)
        self.root_dir = ""
        self.output_dir = ""
        self.records = []
        self.worker = None
        config_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        self.config_path = config_root / "config.json"
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            self.config = {}
        self._build_ui()
        self._style()
        self.log("Ready. Select a source folder and scan before processing.")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        titlebox = QVBoxLayout()
        title = QLabel("VEHICLE DEBADGER")
        title.setObjectName("title")
        subtitle = QLabel("Batch inspection • Safe backups • Texture & 3D workflow")
        subtitle.setObjectName("subtitle")
        titlebox.addWidget(title)
        titlebox.addWidget(subtitle)
        header.addLayout(titlebox)
        header.addStretch()
        self.scan_btn = QPushButton("Scan Vehicles")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self.scan)
        header.addWidget(self.scan_btn)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.settings)
        header.addWidget(self.settings_btn)
        outer.addLayout(header)

        paths = QGridLayout()
        paths.setHorizontalSpacing(10)
        paths.setVerticalSpacing(8)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Select folder containing addon/replace vehicle resources…")
        self.source_edit.setReadOnly(True)
        source_btn = QPushButton("Browse…")
        source_btn.clicked.connect(self.choose_source)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Separate workspace/output folder (never use live resources)")
        self.output_edit.setReadOnly(True)
        output_btn = QPushButton("Browse…")
        output_btn.clicked.connect(self.choose_output)
        paths.addWidget(QLabel("SOURCE FOLDER"), 0, 0)
        paths.addWidget(self.source_edit, 0, 1)
        paths.addWidget(source_btn, 0, 2)
        paths.addWidget(QLabel("WORKSPACE"), 1, 0)
        paths.addWidget(self.output_edit, 1, 1)
        paths.addWidget(output_btn, 1, 2)
        paths.setColumnStretch(1, 1)
        outer.addLayout(paths)

        self.stats = QGridLayout()
        self.stat_labels = {}
        for col, (key, label) in enumerate([
            ("assets", "ASSETS FOUND"), ("models", "3D MODELS"), ("textures", "TEXTURE FILES"), ("review", "NEEDS REVIEW")
        ]):
            card = QFrame()
            card.setObjectName("statCard")
            lay = QVBoxLayout(card)
            number = QLabel("—")
            number.setObjectName("statNumber")
            caption = QLabel(label)
            caption.setObjectName("statCaption")
            lay.addWidget(number)
            lay.addWidget(caption)
            self.stats.addWidget(card, 0, col)
            self.stat_labels[key] = number
        outer.addLayout(self.stats)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        inventory_tab = QWidget()
        inv_layout = QVBoxLayout(inventory_tab)
        toolbar = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by file, resource, or review note…")
        self.filter_edit.textChanged.connect(self.populate_table)
        toolbar.addWidget(self.filter_edit, 1)
        self.kind_filter = QComboBox()
        self.kind_filter.addItems(["All asset types", "3D model", "Texture dictionary", "Image texture", "Vehicle metadata", "Resource manifest", "Other"])
        self.kind_filter.currentTextChanged.connect(self.populate_table)
        toolbar.addWidget(self.kind_filter)
        inv_layout.addLayout(toolbar)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Asset", "Resource", "Type", "Size", "SHA-256", "Review / next step"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        inv_layout.addWidget(self.table)
        self.tabs.addTab(inventory_tab, "Asset Inventory")

        workflow_tab = QWidget()
        wf = QVBoxLayout(workflow_tab)
        intro = QLabel("Safe batch workflow")
        intro.setObjectName("sectionTitle")
        wf.addWidget(intro)
        self.backup_check = QCheckBox("Create a timestamped backup of the source folder before any external edits")
        self.backup_check.setChecked(True)
        self.backup_check.setEnabled(False)  # no in-place edits in this initial safe workflow
        wf.addWidget(self.backup_check)
        self.copy_btn = QPushButton("Create Workspace Copy + Manifest")
        self.copy_btn.clicked.connect(self.create_workspace)
        wf.addWidget(self.copy_btn)
        self.texture_btn = QPushButton("Prepare Texture Review Queue")
        self.texture_btn.clicked.connect(self.prepare_texture_queue)
        wf.addWidget(self.texture_btn)
        self.model_btn = QPushButton("Prepare 3D Model Review Queue")
        self.model_btn.clicked.connect(self.prepare_model_queue)
        wf.addWidget(self.model_btn)
        self.export_btn = QPushButton("Generate Export Readiness Report")
        self.export_btn.clicked.connect(self.export_report)
        wf.addWidget(self.export_btn)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        wf.addWidget(self.progress)
        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setPlaceholderText("Batch actions and review queue details appear here.")
        wf.addWidget(self.queue_text, 1)
        self.tabs.addTab(workflow_tab, "Batch Workflow")

        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "Activity Log")

        footer = QLabel("Non-destructive by design • Unknown binary assets are never modified automatically")
        footer.setObjectName("footer")
        outer.addWidget(footer)

    def _style(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background:#11151d; color:#e8edf5; font-size:13px; }
        QLabel#title { font-size:25px; font-weight:800; letter-spacing:1px; color:#f4f7fb; }
        QLabel#subtitle, QLabel#footer { color:#9aa8ba; }
        QLabel#footer { padding-top:4px; }
        QLabel#statNumber { font-size:27px; font-weight:800; color:#f6f8fb; }
        QLabel#statCaption { color:#9aa8ba; font-size:10px; font-weight:700; letter-spacing:1px; }
        QLabel#sectionTitle { font-size:18px; font-weight:700; padding:4px 0 8px; }
        QFrame#statCard { background:#1a202b; border:1px solid #2b3544; border-radius:12px; }
        QLineEdit, QComboBox, QTextEdit, QTableWidget { background:#171d27; border:1px solid #303b4b; border-radius:7px; padding:7px; selection-background-color:#46566b; }
        QTableWidget { gridline-color:#293343; }
        QHeaderView::section { background:#202836; color:#cbd5e1; border:0; border-bottom:1px solid #364152; padding:8px; font-weight:700; }
        QPushButton { background:#242d3b; border:1px solid #394659; border-radius:8px; padding:9px 13px; font-weight:650; }
        QPushButton:hover { background:#303b4d; }
        QPushButton#primary { background:#e4e9ef; color:#10151c; border-color:#e4e9ef; }
        QPushButton#primary:hover { background:#ffffff; }
        QPushButton:disabled { color:#687587; background:#1b222d; }
        QTabWidget::pane { border:1px solid #303b4b; border-radius:8px; top:-1px; }
        QTabBar::tab { background:#1a202b; padding:10px 16px; margin-right:4px; border-top-left-radius:7px; border-top-right-radius:7px; color:#aab6c6; }
        QTabBar::tab:selected { background:#293444; color:#fff; }
        QProgressBar { background:#171d27; border:1px solid #303b4b; border-radius:6px; height:13px; text-align:center; }
        QProgressBar::chunk { background:#91a5bb; border-radius:5px; }
        QCheckBox { spacing:9px; padding:8px; }
        """)
        self.setFont(QFont("Segoe UI", 10))

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{stamp}] {message}")

    def choose_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select vehicle source folder")
        if path:
            self.root_dir = path
            self.source_edit.setText(path)
            self.log(f"Source folder selected: {path}")

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select separate workspace/output folder")
        if path:
            self.output_dir = path
            self.output_edit.setText(path)
            self.log(f"Workspace selected: {path}")

    def scan(self):
        if not self.root_dir:
            QMessageBox.information(self, "Choose source", "Choose the folder containing your vehicle resources first.")
            return
        self.scan_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log("Starting recursive scan. Source files will not be modified.")
        self.worker = ScanWorker(self.root_dir)
        self.worker.progress.connect(self.on_scan_progress)
        self.worker.finished_records.connect(self.on_scan_finished)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.finished.connect(lambda: self.scan_btn.setEnabled(True))
        self.worker.start()

    def on_scan_progress(self, value, text):
        self.progress.setValue(value)
        self.statusBar().showMessage(text)

    def on_scan_finished(self, records):
        self.records = records
        self.populate_table()
        self.stat_labels["assets"].setText(f"{len(records):,}")
        self.stat_labels["models"].setText(f"{sum(1 for r in records if r.kind == '3D model'):,}")
        self.stat_labels["textures"].setText(f"{sum(1 for r in records if r.kind in ('Texture dictionary', 'Image texture')):,}")
        self.stat_labels["review"].setText(f"{sum(1 for r in records if r.kind in ('3D model', 'Texture dictionary', 'Image texture')):,}")
        self.log(f"Scan complete: {len(records):,} relevant assets found.")
        self.queue_text.append(f"Scan complete at {datetime.now().isoformat(timespec='seconds')}\nRelevant assets: {len(records)}\n")
        self.tabs.setCurrentIndex(0)

    def on_scan_failed(self, error):
        self.log(f"Scan failed: {error}")
        QMessageBox.critical(self, "Scan failed", error)

    def populate_table(self):
        query = self.filter_edit.text().strip().lower()
        kind = self.kind_filter.currentText()
        if kind == "All asset types":
            kind = None
        filtered = [r for r in self.records if (not query or query in r.relative_path.lower() or query in r.resource.lower() or query in r.review.lower()) and (not kind or r.kind == kind)]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        for row, rec in enumerate(filtered):
            values = [rec.relative_path, rec.resource, rec.kind, readable_size(rec.size), rec.sha256[:16] + "…", rec.review]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if col == 5 and rec.kind in ("3D model", "Texture dictionary", "Image texture"):
                    item.setForeground(QColor("#f2c879"))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    def require_scan_and_output(self):
        if not self.records:
            QMessageBox.information(self, "Scan first", "Scan the source folder before running batch actions.")
            return False
        if not self.output_dir:
            QMessageBox.information(self, "Choose workspace", "Choose a separate workspace/output folder first.")
            return False
        try:
            if Path(self.output_dir).resolve() == Path(self.root_dir).resolve():
                QMessageBox.warning(self, "Unsafe workspace", "Workspace must be different from the source folder.")
                return False
        except Exception:
            pass
        return True

    def create_workspace(self):
        if not self.require_scan_and_output():
            return
        dest = Path(self.output_dir) / f"Debadger_Workspace_{now_tag()}"
        source = Path(self.root_dir)
        try:
            self.log(f"Creating workspace copy: {dest}")
            dest.mkdir(parents=True, exist_ok=False)
            # Copy only the resource tree into a source subfolder to make it easy to compare.
            target = dest / "source_copy"
            shutil.copytree(source, target, dirs_exist_ok=True)
            manifest = {
                "app": APP_NAME,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source": str(source),
                "source_copy": str(target),
                "asset_count": len(self.records),
                "assets": [asdict(r) for r in self.records],
                "note": "Copy created; no debadging edits have been applied automatically."
            }
            (dest / "inventory_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            (dest / "README_NEXT_STEPS.txt").write_text(
                "Workspace copy created safely.\n"
                "Texture dictionaries (.ytd): export textures with a compatible tool, edit approved image textures, then re-import.\n"
                "3D models (.yft): inspect in a compatible GTA V model workflow (e.g. CodeWalker + Blender/Sollumz).\n"
                "Validate all changed assets in a local FiveM test server before deployment.\n",
                encoding="utf-8"
            )
            self.queue_text.append(f"Workspace created: {dest}\nSource copy: {target}\nManifest: inventory_manifest.json\n")
            self.log("Workspace copy and inventory manifest created successfully.")
            QMessageBox.information(self, "Workspace created", f"Safe workspace created:\n{dest}\n\nNo original files were modified.")
        except Exception as e:
            self.log(f"Workspace creation failed: {e}")
            QMessageBox.critical(self, "Workspace creation failed", str(e))

    def prepare_texture_queue(self):
        if not self.require_scan_and_output():
            return
        items = [asdict(r) for r in self.records if r.kind in ("Texture dictionary", "Image texture")]
        self._write_queue("texture_review_queue.json", items, "Texture Review Queue")
        self.queue_text.append(f"Texture review queue prepared: {len(items)} assets.\n")
        self.log(f"Texture review queue prepared ({len(items)} assets).")
        self.tabs.setCurrentIndex(1)

    def prepare_model_queue(self):
        if not self.require_scan_and_output():
            return
        items = [asdict(r) for r in self.records if r.kind == "3D model"]
        self._write_queue("model_review_queue.json", items, "3D Model Review Queue")
        self.queue_text.append(f"3D model review queue prepared: {len(items)} assets.\n")
        self.log(f"3D model review queue prepared ({len(items)} assets).")
        self.tabs.setCurrentIndex(1)

    def _write_queue(self, filename, items, title):
        dest = Path(self.output_dir) / f"Debadger_Queues_{now_tag()}"
        dest.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": title,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": self.root_dir,
            "count": len(items),
            "assets": items,
            "instructions": "Review each asset. This queue does not itself remove badges from proprietary GTA V binary formats."
        }
        (dest / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def export_report(self):
        if not self.require_scan_and_output():
            return
        dest = Path(self.output_dir) / f"Debadger_Report_{now_tag()}"
        dest.mkdir(parents=True, exist_ok=True)
        summary = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": self.root_dir,
            "total_assets": len(self.records),
            "models": sum(r.kind == "3D model" for r in self.records),
            "texture_dictionaries": sum(r.kind == "Texture dictionary" for r in self.records),
            "image_textures": sum(r.kind == "Image texture" for r in self.records),
            "metadata": sum(r.kind == "Vehicle metadata" for r in self.records),
            "manifest_files": sum(r.kind == "Resource manifest" for r in self.records),
            "readiness": "Inventory complete; actual debadging and in-game validation are still required.",
            "assets": [asdict(r) for r in self.records]
        }
        (dest / "export_readiness_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        with (dest / "export_readiness_report.csv").open("w", encoding="utf-8", newline="") as f:
            import csv
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.records[0]).keys()) if self.records else ["path"])
            writer.writeheader()
            for rec in self.records:
                writer.writerow(asdict(rec))
        self.queue_text.append(f"Readiness report created: {dest}\nNo assets are marked debadged automatically.\n")
        self.log(f"Export readiness report written: {dest}")
        QMessageBox.information(self, "Report generated", f"Report saved to:\n{dest}")

    def settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config = dlg.values()
            try:
                self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
                self.log("Pipeline settings saved.")
            except Exception as e:
                QMessageBox.warning(self, "Settings not saved", str(e))

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = DebadgerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
