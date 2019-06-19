from PyQt5.QtCore import Qt, QTimer, QSortFilterProxyModel, pyqtSignal, QDateTime, QModelIndex, QItemSelectionModel
from PyQt5.QtWidgets import (QApplication, QDialog, QTableWidget, QGridLayout, QTableWidgetItem, QTableView, QLineEdit, QFormLayout, QPushButton, QHeaderView, QTextEdit, QScrollArea, QWidget, QComboBox, QAbstractItemView)
from PyQt5.QtSql import QSqlDatabase, QSqlQuery, QSqlTableModel, QSqlRecord
from PyQt5.QtGui import QFontMetrics
import pandas as pd
import webbrowser, requests
import os, subprocess, webbrowser, re, collections, hashlib, random, json 
import feedparser
import scholarly
import logging
import bibtexparser
from PyPDF2 import PdfFileReader

logging.basicConfig(filename='logfile.log',level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

pd.set_option('mode.chained_assignment', None)

#headers from scholarly
_GOOGLEID = hashlib.md5(str(random.random()).encode('utf-8')).hexdigest()[:16]
_COOKIES = {'GSP': 'ID={0}:CF=4'.format(_GOOGLEID)}
_HEADERS = {
    'accept-language': 'en-US,en',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/41.0.2272.76 Chrome/41.0.2272.76 Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml'
    }


columns = {'id': 'INTEGER PRIMARY KEY', 'title':'TEXT', 'author':'TEXT', 'date':'INTEGER', 'document':'TEXT', 'form':'TEXT', 'tags':'TEXT', 'notes':'TEXT', 'opened':'TIMESTAMP', 'created':'TIMESTAMP', 'abstract':'TEXT', 'refs':'TEXT', 'link':'TEXT', 'length':'INTEGER', 'journal':'TEXT', 'publisher':'TEXT', 'pages':'TEXT', 'number':'TEXT', 'volume':'TEXT', 'doi':'TEXT'}

class Window(QDialog):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        self.showMaximized()
        self.database = Database('database.db')
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
        self.wgt
        self.flayout2 = FormLayout(columns, self.filteredModel, self.view)
        self.wgt.setLayout(self.flayout2)
        self.scrollarea = QScrollArea()
        self.scrollarea.setWidget(self.wgt)
#        self.scrollarea.horizontalScrollBar().setEnabled(False) 

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
            logging.info('Removed row with title entry: ' + str(self.filteredModel.index(index.row(), 1)))
            # to implement:
            # ind = list(columns.keys()).index('document')
            # document = self.filteredModel.index(index.row(), ind)
            # ask if remove file: os.remove(os.path.join('temp', document))
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
        self.model = QSqlTableModel()
        self.model.setTable('literature')
        self.model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.model.select()

        self.filteredModel = SortFilterProxyModel()
        self.filteredModel.setSourceModel(self.model)

        for index, column in enumerate(columns):
            self.model.setHeaderData(index, Qt.Horizontal, column)
        self.view = QTableView()
        self.view.setSortingEnabled(True)
        self.view.setModel(self.filteredModel)
        self.view.doubleClicked.connect(self.openDocument)
        self.view.clicked.connect(self.openView)
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
        if 'pdf' in fieldname:
            path = os.path.join('temp',y.data())
            if os.path.exists(path):
                command = 'evince "{}"'.format(path)
                subprocess.Popen(command,shell=True)
                ind = list(columns.keys()).index('opened')
                indexx = self.filteredModel.index(y.row(), ind)
                self.filteredModel.setData(indexx, QDateTime.currentDateTime())
                logging.info('Open document: '+ path)
                
            else:
                print('file not found')
        elif 'http' in fieldname:
            webbrowser.open(fieldname, new=2)

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
                self.setItem(i,j,QTableWidgetItem(str(dataframe.iloc[i, j])))
        self.setHorizontalHeaderLabels(dataframe.columns)
        self.setColumnWidth(0, 300)
        self.setColumnWidth(1, 150)

class Window2(QDialog):
    def __init__(self, model, parent=None):
        super(Window2, self).__init__(parent)

        self.model = model
        self.mainLayout = QGridLayout()
        self.mainLayout.setColumnStretch(0,1)
        self.mainLayout.setColumnStretch(1,4)

        self.flayout = QFormLayout()
        self.flayout.addRow('title', QLineEdit())
        self.flayout.addRow('author', QLineEdit())
        self.flayout.addRow('year', QLineEdit())
        self.flayout.addRow('abstract', QLineEdit())
        self.comboBox = QComboBox()
        self.comboBox.addItems(['arxiv', 'gscholar'])
        self.flayout.addRow('source', self.comboBox)

        self.table = TableWidget()        
        
        self.setFixedSize(1000, 600)
        
        button1 = QPushButton()
        button1.setText("Search")
        button1.clicked.connect(self.search)
        
        button2 = QPushButton()
        button2.setText("Save")
        button2.clicked.connect(self.save)

        self.setWindowTitle('Search')
        self.mainLayout.addLayout(self.flayout, 0, 0)
        self.mainLayout.addWidget(self.table, 0, 1)
        self.mainLayout.addWidget(button1, 1, 0)
        self.mainLayout.addWidget(button2, 1, 1)   
        
        self.setLayout(self.mainLayout)
        
    def getInputData(self):
        inputData ={self.flayout.itemAt(2*i).widget().text():self.flayout.itemAt(2*i+1).widget().text() for i in range(int(self.flayout.count() / 2)-1)}
        inputData['source'] = self.comboBox.currentText()
        return inputData

    def search(self):
        inputData = self.getInputData()
        if inputData['source'] == 'arxiv':
            df = self.arxiv(inputData)
        elif inputData['source'] == 'gscholar':
            df = self.gscholar(inputData)
        
        self.table.fillTable(df)
    
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
        author = ', '.join(re.findall(r'(\w*)(?:$|,)', new_data.get('author'))[:-1])
        title = re.sub(r"[^a-zA-Z0-9]+", ' ', new_data.get('title'))
        date = new_data.get('date') if new_data.get('date') else ''
        filename = date + ' ' +  title + ' - ' + author + '.pdf'
        path = os.path.join('temp', filename)
        if not os.path.exists(path):
            response = requests.get(new_data['document'])
            with open(path, 'wb') as f:
                f.write(response.content)
        new_data['document'] = filename
        new_data['length'] = PdfFileReader(open(path,'rb')).getNumPages()
        return new_data
        

    def arxiv(self, inputData):
        logging.info('search arxiv with values: ' + str(inputData))
        url = 'http://export.arxiv.org/api/query?search_query=au:"{}"+AND+ti:"{}"+AND+abs:"{}"'.format(inputData['author'], inputData['title'], inputData['abstract'])
        raw_data = requests.get(url).text
        data = feedparser.parse(raw_data)
        data2 = pd.DataFrame(data.get('entries'))
        if data2.empty:
            return pd.DataFrame()
        info = ['title', 'summary']
        meta_info = {'authors':'name', 'tags':'term'}
        data3 = data2[info]
        for column in meta_info:
            data3[column] = data2[column].apply(lambda x: ', '.join([entry.get(meta_info[column]) for entry in x]))
        data3['published'] = data2['published'].apply(lambda x: x[:4])
        
        def extract(x, value):
            for entry in x:
                if value in entry['href']:
                    return entry['href']
            else:
                return ''
        data3['link'] = data2['links'].apply(lambda x: extract(x, '/abs/'))
        data3['document'] = data2['links'].apply(lambda x: extract(x, '/pdf/'))
   
        data3.columns = ['title', 'abstract', 'author', 'tags', 'date', 'link', 'document']

        return data3[['title', 'author', 'date', 'tags', 'abstract', 'link', 'document']]

    def gscholar(self, inputData):
        logging.info('search gscholar with values: ' + str(inputData))
        inputFormatted = ' '.join(inputData.values())
        search_query = scholarly.search_pubs_query(inputFormatted)
        
        data = pd.DataFrame()
        count = 0
        for entry in search_query:
            print(entry)
            if count < 4:
                print('a')
                datapoint = {'title': entry.bib.get('title'),
                'author': entry.bib.get('author'),
                'abstract': entry.bib.get('abstract'), 
                'link': entry.bib.get('url')}
                urlBibfile = entry.url_scholarbib
                response = requests.get(urlBibfile, headers=_HEADERS, cookies=_COOKIES)
                if response.status_code == 200:
                    bibDictionary = bibtexparser.loads(response.text).entries[0]
                    datapoint['date'] = bibDictionary.get('year')
                    datapoint['journal'] = bibDictionary.get('journal')
                    datapoint['form'] = bibDictionary.get('ENTRYTYPE')
                    datapoint['pages'] = bibDictionary.get('pages')
                    datapoint['number'] = bibDictionary.get('number')
                    datapoint['volume'] = bibDictionary.get('volume')
                    datapoint['publisher'] = bibDictionary.get('publisher')
                    data = data.append(datapoint, ignore_index=True)
                count = count + 1
        return data       

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
        index = self.view.selectionModel().selectedIndexes()[0].row()
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
        new_docs = set(os.listdir('temp')) - set(docs)
        for filename in new_docs:
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
            logging.info("Added " + str(data))
            data['length'] = PdfFileReader(open(os.path.join('temp', data['document']),'rb')).getNumPages()
            data['created'] = QDateTime.currentDateTime()
            self.insert(data)

    def insert(self, data):
        empty_data = {column: '' for column in columns}
        full_data = {**empty_data, **data}
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
