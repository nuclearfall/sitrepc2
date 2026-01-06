from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTableView, QPlainTextEdit, QLabel, 
    QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt

class DomReviewWindow(QMainWindow):
    def __init__(self, runs_data):
        super().__init__()
        self.setWindowTitle("DOM Review Workspace")
        
        # Main horizontal splitter (left panel and right panel)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left vertical splitter (for list and text)
        left_splitter = QSplitter(Qt.Vertical)
        
        # Table view for LSS runs list (top of left panel)
        self.model = LssRunModel(runs_data, parent=self)
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)  # hide row numbers
        
        # Add the table view to the left splitter
        left_splitter.addWidget(self.table_view)
        
        # Text area for ingest post text (bottom of left panel)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        left_splitter.addWidget(self.text_edit)
        
        # Optionally, set initial splitter sizes or stretch factors for left panel
        left_splitter.setStretchFactor(0, 2)   # list gets 2/3 of left splitter by default
        left_splitter.setStretchFactor(1, 1)   # text gets 1/3 of left splitter
        
        # Right vertical splitter (for DOM tree view and node detail placeholders)
        right_splitter = QSplitter(Qt.Vertical)
        # Placeholder for DOM tree view area
        self.dom_tree_placeholder = QLabel("👆 Select a run to load DOM snapshot")
        self.dom_tree_placeholder.setAlignment(Qt.AlignCenter)
        right_splitter.addWidget(self.dom_tree_placeholder)
        # Placeholder for node detail view area
        self.node_detail_placeholder = QLabel("Node details will appear here")
        self.node_detail_placeholder.setAlignment(Qt.AlignCenter)
        right_splitter.addWidget(self.node_detail_placeholder)
        
        # Disallow collapsing the placeholders completely (optional)
        right_splitter.setCollapsible(0, False)
        right_splitter.setCollapsible(1, False)
        # Set stretch factors for right panel (give more space to DOM tree area)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        
        # Add both left and right panels to the main splitter
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)
        # Set stretch factors for main splitter (give more width to right panel)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        
        # Set the main splitter as the central widget of the window
        self.setCentralWidget(main_splitter)
        
        # Connect selection change in the list to handler
        # This will call self.on_run_selected whenever the current selected row changes
        self.table_view.selectionModel().currentChanged.connect(self.on_run_selected)
        
        # If there are runs, select the first one by default to show initial details
        if self.model.rowCount() > 0:
            first_index = self.model.index(0, 0)
            self.table_view.setCurrentIndex(first_index)
    
    def on_run_selected(self, current_index, previous_index):
        """Slot called when a new LSS run is selected in the list."""
        run = self.model.getRun(current_index)
        if not run:
            return
        # Fetch the ingest post text for the selected run.
        # In a real application, replace this with a database query using the provided SQL.
        run_id = run.get("id")
        text = ingest_texts.get(run_id, "<No text found>")
        self.text_edit.setPlainText(text if text is not None else "")
        
        # Prepare to display the DOM tree in the center panel (stub for now).
        # This could call a method to load the DOM snapshot and populate a tree view.
        # For now, just update the placeholder label.
        self.dom_tree_placeholder.setText(f"DOM tree for run {run_id} would be displayed here.")
        # Clear or reset node detail placeholder when a new run is selected
        self.node_detail_placeholder.setText("Node details will appear here")
