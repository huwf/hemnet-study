# Hemnet house price data analysis

This is a repository for the DIT-862 Applied Machine Learning project I performed in the Autumn term 2021 at the University of Gothenburg.

There are three parts to this project.   There is some code written in Python 3, and two presentations which are made using Jupyter Notebook.  

* Firstly, some code for web scraping the hemnet.se page.  I obeyed robots.txt, and left a gap in between each request. 
* Some data preparation.  This merged the data from Hemnet with granular data from the Swedish Election Authority [Valmyndigheten](https://www.val.se).  This was kept separate from the main notebook because even cutting it down, it takes quite a while to run.
* Statistical analysis and machine learning of various phenomena related to the data extracted.  Sadly, it was not possible to make many useful conclusions because the data was not detailed enough (e.g no photos of rooms in the sold houses) but it was fun to do.
