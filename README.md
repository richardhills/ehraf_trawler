# ehraf_trawler

To install, follow these instructions:

1. Download the code from https://github.com/richardhills/ehraf_trawler/archive/master.zip
2. unzip the file somewhere that you will find it easy to use in future.
3. Open a terminal and type "gcc", followed by return. It will ask to install developer tools - click yes.
4. Install "brew" by visiting http://brew.sh/ and following the instructions.
5. On the terminal, run "brew install python"
6. On the terminal, run "pip install virtualenvwrapper"
7. On the terminal, run the following commands:
echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc
echo 'source /usr/local/bin/virtualenvwrapper.sh' >> ~/.bashrc
source ~/.bashrc
8. On a new terminal, run "mkvirtualenv ehraf"
9. On the same terminal, change your working directory to where you downloaded the code using "cd".
10. Type "cd main"
11. Run "pip install -r requirements.txt"

To run the trawler, for a particular $QUERY, run:

python trawler.py $QUERY

The output will be in results.xlsx
