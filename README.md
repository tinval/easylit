# easylit
Database  GUI to store literature

# How to make an executable app for linux

```pyinstaller --onefile frontend.py```

Then you must add the sqlite drivers to the folder `dist` which gets created during the `pyinstaller` process.
You can find it by searching

```find ~ -name "*sqldriver*"```

It should be in a folder `Qt/plugins`.

Then when copying the executable to a different place you may need to change running permission:

```chmod +x frontend3```
