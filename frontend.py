from PyQt5.QtCore import Qt, QTimer, QSortFilterProxyModel, pyqtSignal, QDateTime, QModelIndex, QItemSelectionModel
from PyQt5.QtWidgets import (QApplication, QDialog, QTableWidget, QGridLayout, QTableWidgetItem, QTableView, QLineEdit, QFormLayout, QPushButton, QHeaderView, QTextEdit, QScrollArea, QWidget, QComboBox, QAbstractItemView, QMessageBox, QLabel)
from PyQt5.QtSql import QSqlDatabase, QSqlQuery, QSqlTableModel, QSqlRecord
from PyQt5.QtGui import QFontMetrics
import pandas as pd
import requests
import os, subprocess, webbrowser, re, collections, json 
import logging
import bibtexparser
from PyPDF2 import PdfFileReader
import yaml
from send2trash import send2trash
import platform
from scrapers import Scraper

_HEADERS = {
    'accept-language': 'en-US,en',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/41.0.2272.76 Chrome/41.0.2272.76 Safari/537.36'
             }

with open("config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

logging.basicConfig(filename='logfile.log',level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

pd.set_option('mode.chained_assignment', None)

SortRole = Qt.UserRole

columns = {'id': 'INTEGER PRIMARY KEY', 'title':'TEXT', 'author':'TEXT', 'date':'INTEGER', 'document':'TEXT', 'form':'TEXT', 'tags':'TEXT', 'notes':'TEXT', 'opened':'TIMESTAMP', 'created':'TIMESTAMP', 'abstract':'TEXT', 'refs':'TEXT', 'link':'TEXT', 'length':'INTEGER', 'journal':'TEXT', 'publisher':'TEXT', 'pages':'TEXT', 'number':'TEXT', 'volume':'TEXT', 'doi':'TEXT'}


class Window(QDialog):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.showMaximized()
        self.database = Database(cfg['database_name'])
        self.mainLayout = QGridLayout()
        self.mainLayout.setColumnStretch(0,2)
        self.mainLayout.setColumnStretch(1,4)
        self.mainLayout.setColumnStretch(2,4)
        self.mainLayout.setColumnStretch(3,4)
        self.prepareTable()
        flayout = QFormLayout()
        for index, column in enumerate(columns):
            if column != 'id':
                le = QLineEdit()
                flayout.addRow(column, le)
                le.textChanged.connect(lambda text, col=index: self.filteredModel.setFilterByColumn(text, col))
        
        self.wgt = QWidget()
        self.flayout2 = FormLayout(columns, self.filteredModel, self.view)
        self.wgt.setLayout(self.flayout2)
        self.scrollarea = QScrollArea()
        self.scrollarea.setWidget(self.wgt)

        button1 = QPushButton()
        button1.setText('Remove rows')
        button1.clicked.connect(self.removeRow)

        button2 = QPushButton()
        button2.setText('Complete')
        button2.clicked.connect(self.openWindow3)

        button3 = QPushButton()
        button3.setText('New Search')
        button3.clicked.connect(self.openWindow2)
     
        self.mainLayout.addLayout(flayout, 0, 0, 1, 1)
        self.mainLayout.addWidget(self.view, 0, 1, 1, 2)
        self.mainLayout.addWidget(self.scrollarea, 0, 3, 1, 1)
        self.mainLayout.addWidget(button1, 1, 1)
        self.mainLayout.addWidget(button2, 1, 2)
        self.mainLayout.addWidget(button3, 1, 3)

        self.setLayout(self.mainLayout)
        self.setWindowTitle('Easylit')

    def removeRow(self):
        indexes = self.view.selectionModel().selectedIndexes()
        for index in indexes:
            if QMessageBox.Yes == QMessageBox(QMessageBox.Information, '', 'Do you really want to delete these elements?', QMessageBox.Yes | QMessageBox.No).exec_():
                document = self.filteredModel.index(index.row(), 4).data()
                if 'pdf' in document:
                    try:
                        send2trash(os.path.join(cfg['temp'], document))
                    except:
                        try:
                            os.remove(os.path.join(cfg['temp'], document))
                        except:
                            msgBox = QMessageBox()
                            msgBox.setText("Error: No file found")
                            msgBox.exec_()
                logging.info('Removed row with title entry: ' + str(self.filteredModel.index(index.row(), 1).data()))
                self.filteredModel.removeRow(index.row())
        self.model.select()


    def openWindow2(self):
        window2 = Window2(self.model)
        window2.exec_()

    def openWindow3(self):
        window3 = Window3(self.model, self.flayout2)
        window3.exec_()

    def filtering(self, x):
        self.filteredModel.setFilterRegExp(x)

    def prepareTable(self):
        self.model = SqlTableModel()
        self.model.setTable('literature')
        self.model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.model.select()
        while self.model.canFetchMore():
            self.model.fetchMore()
        self.filteredModel = SortFilterProxyModel()
        self.filteredModel.setSourceModel(self.model)
        self.filteredModel.setSortRole(SortRole)

        for index, column in enumerate(columns):
            self.model.setHeaderData(index, Qt.Horizontal, column)
        self.view = QTableView()
        self.view.setSortingEnabled(True)
        self.view.setModel(self.filteredModel)
        self.view.doubleClicked.connect(self.openDocument)
        self.view.clicked.connect(self.openView)
        self.view.selectionModel().selectionChanged.connect(self.openView)
        self.view.setWordWrap(False)
        self.view.setColumnWidth(1, 300)
        self.view.setColumnWidth(2, 200)
        header = self.view.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(13, QHeaderView.ResizeToContents)

    def openDocument(self, y):
        fieldname = y.data()
        if not isinstance(fieldname, str):
            return
        if 'http' in fieldname:
            webbrowser.open(fieldname, new=2)
        elif '.pdf' in fieldname:
            path = os.path.join(cfg['temp'],y.data())
            if os.path.exists(path):
                if platform.system() == 'Linux':
                    command = 'evince "{}"'.format(path)
                    subprocess.Popen(command,shell=True)
                else:
                    webbrowser.open_new(r'file://{}'.format(path))
                ind = list(columns.keys()).index('opened')
                indexx = self.filteredModel.index(y.row(), ind)
                self.filteredModel.setData(indexx, QDateTime.currentDateTime())
                logging.info('Open document: '+ path)
            else:
                print('file not found')

    def openView(self, y):
        self.flayout2.setAllValues()


class TableWidget(QTableWidget):
    def __init__(self, parent=None):
        super(TableWidget, self).__init__(parent)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setWordWrap(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
    
    def fillTable(self, dataframe):
        self.setColumnCount(len(dataframe.columns))
        self.setRowCount(len(dataframe.index))
        for i in range(len(dataframe.index)):
            for j in range(len(dataframe.columns)):
                item = QTableWidgetItem(str(dataframe.iloc[i, j]))
                item.setToolTip(str(dataframe.iloc[i, j]))
                self.setItem(i,j,item)
        self.setHorizontalHeaderLabels(dataframe.columns)
        self.setColumnWidth(0, 300)
        self.setColumnWidth(1, 150)

class Window2(QDialog):
    def __init__(self, model, parent=None):
        super(Window2, self).__init__(parent)

        self.model = model
        self.mainLayout = QGridLayout()
        self.mainLayout.setColumnStretch(0,1)
        self.mainLayout.setColumnStretch(1,3)
        self.mainLayout.setColumnStretch(2,3)

        self.flayout = QFormLayout()
        self.flayout.addRow('title', QLineEdit())
        self.flayout.addRow('author', QLineEdit())
        self.flayout.addRow('abstract', QLineEdit())
        self.comboBox = QComboBox()
        self.comboBox.addItems(Scraper.scrapers)
        self.flayout.addRow('source', self.comboBox)

        self.table = TableWidget()
        self.table.doubleClicked.connect(self.openDocument)
        
        self.setFixedSize(1000, 600)
        
        button1 = QPushButton()
        button1.setText("Search")
        button1.clicked.connect(self.search)
        
        button2 = QPushButton()
        button2.setText("Save")
        button2.clicked.connect(self.save)

        self.button3 = QPushButton()
        self.button3.setText("Next")
        self.button3.clicked.connect(self.next_results)
        self.button3.setVisible(False)
        
        self.button4 = QPushButton()
        self.button4.setText("Previous")
        self.button4.clicked.connect(self.previous_results)
        self.button4.setVisible(False)

        self.label = QLabel()
        self.label.setVisible(False)

        self.setWindowTitle('Search')
        self.mainLayout.addLayout(self.flayout, 0, 0)
        self.mainLayout.addWidget(self.table, 0, 1, 1, 2)
        self.mainLayout.addWidget(self.label, 1, 0)
        self.mainLayout.addWidget(self.button4, 1, 1)
        self.mainLayout.addWidget(self.button3, 1, 2) 
        self.mainLayout.addWidget(button1, 2, 0)
        self.mainLayout.addWidget(button2, 2, 1, 1, 2)   
        
        self.setLayout(self.mainLayout)
        
    def getInputData(self):
        inputData ={self.flayout.itemAt(2*i).widget().text():self.flayout.itemAt(2*i+1).widget().text() for i in range(int(self.flayout.count() / 2)-1)}
        inputData['source'] = self.comboBox.currentText()
        return inputData

    def search(self):
        inputData = self.getInputData()
        source = inputData.pop('source')
        self.scraper = Scraper(inputData, source)
        logging.info('Scraper search' + str(inputData))
        results = self.scraper.search()        
        self.table.fillTable(results)
        if self.scraper.total > 10:
            self.button3.setVisible(True)
        self.update_label()

    def update_label(self):
        self.label.setText('Page {} of {}'.format(self.scraper.page, int(self.scraper.total/10)+1))
        self.label.setVisible(True)

    def next_results(self):
        self.scraper.page += 1       
        results = self.scraper.search()
        self.table.fillTable(results)
        self.button4.setVisible(True)
        if self.scraper.total <= 10 * self.scraper.page:
            self.button3.setVisible(False)
        self.update_label()

    def previous_results(self):
        self.scraper.page -= 1
        results = self.scraper.search()        
        self.table.fillTable(results)
        self.button3.setVisible(True)
        if self.scraper.page <= 1:
            self.button4.setVisible(False)
        self.update_label()

    def openDocument(self, y):
        if 'http' in y.data():
            webbrowser.open(y.data(), new=2)

    def save(self):
        index = self.table.selectionModel().selectedRows()
        if len(index) > 0:
            new_data = {self.table.horizontalHeaderItem(i).text(): str(self.table.model().index(index[0].row(), i).data()) for i in range(self.table.columnCount())}
            if 'document' in new_data and 'pdf' in new_data['document']:
                new_data = self.save_file(new_data)
            row_index = self.model.rowCount(QModelIndex())
            record = self.model.record()
            record.setGenerated('id', False)
            record.setValue('created', QDateTime.currentDateTime())
            for column in new_data:
                 record.setValue(column, new_data[column])
            self.model.insertRecord(-1, record)
    
    def save_file(self, new_data):
        if 'document' in new_data and len(new_data['document']) > 0:
            author = ', '.join(re.findall(r'(\w*)(?:$|,)', new_data.get('author'))[:-1])
            title = re.sub(r"[^a-zA-Z0-9]+", ' ', new_data.get('title'))
            date = new_data.get('date') if new_data.get('date') else ''
            filename = date + ' ' +  title + ' - ' + author + '.pdf'
            path = os.path.join(cfg['temp'], filename)
            logging.info('Trying to save file ' + filename)
            if not os.path.exists(path):
                response = requests.get(new_data['document'], headers=_HEADERS)
                if response.ok:
                    try:
                        with open(path, 'wb') as f:
                            f.write(response.content)
                        try:
                            new_data['length'] = PdfFileReader(open(path,'rb')).getNumPages()
                        except:
                            display_text = 'Corrupted document ' + filename
                        new_data['document'] = filename
                        display_text = 'Saved document ' + filename
                    except:
                        display_text = 'Dowload document successful, but not possible to save.'
                        new_data['document'] = ''
                else:
                    display_text = 'Dowload document not successful.'
                    new_data['document'] = ''
            else:
                display_text = 'File ' + filename + 'already exists.'
        else:
            display_text = 'There is no document to save.'
        msgBox = QMessageBox()
        msgBox.setText(display_text)
        msgBox.exec_()
        logging.info(display_text)
        return new_data

class Window3(Window2):
    def __init__(self, model, flayout_outer, parent=None):
        Window2.__init__(self, model)
        self.model = model
        self.flayout_outer = flayout_outer
        self.previous_data = self.flayout_outer.getAllValues()
        self.flayout.itemAt(1).widget().setText(self.previous_data['title'])
        self.flayout.itemAt(3).widget().setText(self.previous_data['author'])
    
    def save(self):
        index = self.table.selectionModel().selectedRows()
        if len(index) > 0:
            new_data = {self.table.horizontalHeaderItem(i).text(): str(self.table.model().index(index[0].row(), i).data()) for i in range(self.table.columnCount())}
            if len(self.previous_data['document']) > 0 and 'document' in new_data and 'pdf' in new_data['document']:
                new_data = self.save_file(new_data)
            
            for entry in self.previous_data:
                if len(self.previous_data[entry]) == 0 and new_data.get(entry):
                    self.previous_data[entry] = new_data.get(entry)
            values = list(self.previous_data.values())
            for i in range(len(values)):
                widg = self.flayout_outer.itemAt(2*i+1).widget()
                widg.setText(values[i])
                self.flayout_outer.updateData(i)
                widg.adjust()
        self.close()

class FormLayout(QFormLayout):
    def __init__(self, columns, model, view, parent=None):
        super(FormLayout, self).__init__(parent)
        for index, column in enumerate(columns):
            te = TextEdit()
            te.setLineWrapMode(QTextEdit.WidgetWidth)
            self.addRow(column, te)
        self.model = model
        self.view = view

    def getAllValues(self):
        return {self.itemAt(2*i).widget().text():self.itemAt(2*i+1).widget().toPlainText() for i in range(int(self.count() / 2))}

    def setAllValues(self):
        indices = self.view.selectionModel().selectedIndexes()
        if len(indices) > 0:
            index = indices[0].row()
            values = [str(self.model.index(index, i).data()) for i in range(len(columns))]
            for i in range(int(self.count() / 2)):
                widg = self.itemAt(2*i+1).widget()
                widg.setText(values[i])
                widg.adjust()
                widg.lostFocus.connect(lambda col=i: self.updateData(col))
                widg.textChanged.connect(widg.adjust)

    def updateData(self, column):
        text = self.itemAt(2*column+1).widget().toPlainText()
        indexx = self.view.selectionModel().selectedIndexes()[0].row()
        self.model.setData(self.model.index(indexx, column), text)

class TextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        QTextEdit.__init__(self, *args, **kwargs)
    lostFocus = pyqtSignal()
    
    def focusOutEvent(self, event):
        if event.lostFocus():
            self.lostFocus.emit()
        QTextEdit.focusOutEvent(self, event)

    def adjust(self):
        font = self.document().defaultFont()
        fontMetrics = QFontMetrics(font)
        text = self.toPlainText()
        paragraphs = 0
        for line in text.split('\n'):
            paragraphs += (fontMetrics.size(0, line).width() + 30) // self.width() + 1
        textWidth = self.width()
        textHeight = max(1, paragraphs) * 20 + 10
        self.setMaximumSize(textWidth, textHeight)

class SqlTableModel(QSqlTableModel):
    def __init__(self, *args, **kwargs):
        QSqlTableModel.__init__(self, *args, **kwargs)
    
    def data(self, index, role=Qt.DisplayRole):
        if role == SortRole:
            value = QSqlTableModel.data(self, index, role=Qt.DisplayRole)
            try:
                return int(value)
            except:
                return value 
        else:
            return QSqlTableModel.data(self, index, role)
        

class SortFilterProxyModel(QSortFilterProxyModel):
# from https://stackoverflow.com/questions/47201539/how-to-filter-multiple-column-in-qtableview
    def __init__(self, *args, **kwargs):
        QSortFilterProxyModel.__init__(self, *args, **kwargs)
        self.filters = ['']*18

    def setFilterByColumn(self, regex, column):
        self.filters[column] = regex
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        for index, regex in enumerate(self.filters):
            ix = self.sourceModel().index(source_row, index, source_parent)
            if ix.isValid():
                text = str(self.sourceModel().data(ix))
                if not re.search(regex, text, re.IGNORECASE):
                    return False
        return True

    def data(self, index, role):
        if role == Qt.ToolTipRole:
            return QSortFilterProxyModel.data(self, index, Qt.DisplayRole)
        else:
            return QSortFilterProxyModel.data(self, index, role)
           
    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ToolTip


class Database:
    def __init__(self, name_db):
        self.db = QSqlDatabase.addDatabase('QSQLITE')
        self.db.setDatabaseName(name_db)
        self.db.open()
        values = json.dumps(columns).replace('"', '').replace(':', '')[1:-1]
        query = QSqlQuery()
        queryText = 'CREATE TABLE IF NOT EXISTS literature (' + values + ')'
        query.exec_(queryText)
        logging.info('Connected to database')
        self.update_from_temp()

    def update_from_temp(self):
        query = QSqlQuery()
        queryText = """SELECT document FROM literature"""    
        query.exec_(queryText)
        docs = []
        while (query.next()):
            docs.append(query.value(0))
        new_docs = set(os.listdir(cfg['temp'])) - set(docs)
        for filename in new_docs:
            if not filename.startswith('.'):
                data = {'document': filename}
                try:
                    data['date'] = int(filename[:4])
                    filename = filename[5:]
                except:
                    pass
                data['title'] = filename.split(' - ')[0]
                try:
                    data['author'] = filename.split(' - ')[1].split('.pdf')[0]
                except:
                    pass
                print(filename)
                try:
                    data['length'] = PdfFileReader(open(os.path.join(cfg['temp'], data['document']),'rb')).getNumPages()
                except:
                    print(data['document'] + " corrupted")
                data['created'] =  QDateTime.fromSecsSinceEpoch(os.path.getmtime(os.path.join(cfg['temp'], data['document'])))
                logging.info("Added " + str(data))
                self.insert(data)

    def insert(self, data):
        full_data = {column: '' for column in columns}
        full_data.update(data)
        full_data['id'] = 'NULL'
        query = QSqlQuery()
        queryText = 'INSERT INTO literature VALUES (NULL, ' + str((', ?')*(len(columns) - 1)).replace("'", "")[1:] + ')'  
        query.prepare(queryText)
        for entry in list(full_data.values())[1:]:
            query.addBindValue(entry)
        return query.exec_()

    def update(self, data):
        query = QSqlQuery()
        keys = '=?, '.join(list(data.keys()[1:])) + '=?'
        queryText = 'UPDATE literature SET ' + keys + ' WHERE id = ?'
        query.prepare(queryText)
        for entry in list(data.values())[1:]:
            query.addBindValue(entry)
        query.addBindValue(data['id'])
        return query.exec_()


if __name__ == '__main__':

    import sys
    app = QApplication(sys.argv)
    
    window = Window()
    sys.exit(app.exec_())
