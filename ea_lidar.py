import os
import uuid
import shutil
import glob
import time
import tempfile
import geopandas as gp
from zipfile import ZipFile
import argparse

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from selenium.common.exceptions import ElementNotInteractableException, TimeoutException


import urllib.request
from tqdm.auto import tqdm


def download_tile(zipf, download=False, product='LIDAR Point Cloud', 
                  verbose=True, download_dir=False, headerless=True,
                  browser='chrome', year='latest', all_years=False,
                  print_only=True):
    
    if browser == 'firefox':
        from selenium.webdriver.firefox.options import Options
        # you may need to import these as well
#         from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
#         from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
        
        options = Options()
        options.headless = headerless
        # you may need to set capabilities and loc of binary
#         cap = DesiredCapabilities().FIREFOX
#         cap["marionette"] = True
#         binary = FirefoxBinary('/Users/phil/anaconda2/envs/networkx/bin/firefox')
#         driver = webdriver.Firefox(executable_path='/Users/phil/anaconda2/envs/networkx/bin/geckodriver',
#                                    capabilities=cap,
#                                    firefox_binary=binary)
        driver = webdriver.Firefox(options=options)
    else:
        from selenium.webdriver.chrome.options import Options
        import chromedriver_binary
        
        options = Options()
        options.headless = headerless
        driver = webdriver.Chrome(chromedriver_binary.chromedriver_filename, options=options)

    if verbose: print('...waiting for page to load')
    driver.get("https://environment.data.gov.uk/DefraDataDownload/?Mode=survey")
    wait = WebDriverWait(driver, 50)

    if verbose: print('...waiting for shapefile to load')
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#fileid")))
    driver.find_element_by_css_selector("#fileid").send_keys([zipf])
   
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grid-item-container")))
    try:
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".grid-item-container")))
    except TimeoutException:
        if driver.find_element_by_css_selector( 'div.errorsContainer:nth-child(1)').is_displayed():
            raise Exception("The AOI Polygon uploaded exceeds the maximum number of vertices allowed. Use a less complex polygon The maximum vertex count is : 1000")
    E1 = driver.find_element_by_css_selector(".grid-item-container")

    if verbose: print('...waiting for available products to load') 
    while True: # hack :(
        try:
            E1.click()
        except ElementNotInteractableException as e:
            break

    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#productSelect")))
    products = [x.get_attribute('value') for x in 
                 Select(driver.find_element_by_css_selector('#productSelect')).options]
    
    if product not in products:
        raise Exception('{} not in available products. Available products are: {}'.format(product, ', '.join(products)))

    xP = '//*[@id="productSelect"]/option[{}]'.format(products.index(product) + 1)
    wait.until(EC.presence_of_element_located((By.XPATH, xP)))
    driver.find_element_by_xpath(xP).click()

    years = [x.get_attribute('value') for x in Select(driver.find_element_by_css_selector('#yearSelect')).options]
    if year == 'latest':
        xY = ['//*[@id="yearSelect"]/option[1]']
    elif not all_years:
        if year not in years: raise Exception('no data for {}. Avialable years:'.format(year, ', '.join(years)))
        xY = ['//*[@id="yearSelect"]/option[{}]'.format(years.index(year) + 1)]
    else:
        most_recent = int(years[0])
        available_years = [str(y) for y in range(int(year), most_recent + 1) if str(y) in years]
        if verbose and print_only: print('available years:', ', '.join(available_years))
        xY = ['//*[@id="yearSelect"]/option[{}]'.format(years.index(y) + 1) for y in available_years]

    for xYs in xY:
        current = years[int(xYs.split('[')[-1][:-1]) - 1]
        wait.until(EC.presence_of_element_located((By.XPATH, xYs)))
        driver.find_element_by_xpath(xYs).click()
        linki = 1
        while True:
            try:
                href = driver.find_element_by_css_selector('.data-ready-container > a:nth-child({})'.format(linki)).get_attribute("href")
                file_loc = os.path.join(os.path.split(zipf)[0] if not download_dir else download_dir,
                                        href.split('/')[-1])
                if print_only: 
                    print(href)
                else:
                    if not os.path.isfile(file_loc): download_url(href, file_loc)
                linki += 1
            except:
                if verbose and not print_only: print(linki - 1, 'files downloaded for {}'.format(current))
                break
                
                
class DownloadProgressBar(tqdm):
    
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)
        

def download_url(url, output_path):
    
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

        
def num_vertices(shp):
    
    N = 0    
    for i, row in shp.iterrows():
        if row.geometry.type.startswith("Multi"): # It's better to check if multigeometry
            for part in row.geometry: # iterate over all parts of multigeometry
                N += len(part.exterior.coords)
        else: # if single geometry like point, linestring or polygon
            N += len(row.geometry.exterior.coords)
    return N

def tile_input(shp, args):
    
    osgb = gp.read_file('/Users/phil/python/ea_lidar/shp/OSGB_Grid_5km.shp')
    osgb_sindex = osgb.sindex
    tile_index = [list(osgb_sindex.intersection(row.geometry.bounds)) for row in shp.itertuples()][0]
    for idx in tile_index:
        tmp_shp = gp.GeoDataFrame(geometry=[osgb.loc[idx].geometry])
        if tmp_shp.intersects(shp).values[0]:
            tile_tmp = os.path.join(args.tmp_d, '{}_{}'.format(args.tmp_n, idx))
            gp.GeoDataFrame(geometry=[osgb.loc[idx].geometry]).to_file(tile_tmp + '.shp')
            with ZipFile(os.path.join(args.tmp_d, tile_tmp + '.zip'), 'w') as zipObj: 
                [zipObj.write(f) for f in glob.glob(tile_tmp + '*')]
            download_tile(tile_tmp + '.zip',
                          product=args.product,
                          headerless=False,
                          year=args.year,
                          all_years=args.all_years,
                          browser=args.browser,
                          verbose=args.verbose)
            break
    driver.close()
    

if __name__ == '__main__':
    
    # some arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('extent', type=str, nargs=1, help='path to extent')
    parser.add_argument('--print-only', action='store_true', help='print list of available data')
    parser.add_argument('--odir', type=str, nargs=1, help='directory to store tiles')
    parser.add_argument('--product', '-p', type=str, default='LIDAR Composite DTM',
                        help='choose from "LIDAR Composite DSM", "LIDAR Composite DTM", \
                                          "LIDAR Point Cloud", "LIDAR Tiles DSM", \
                                          "LIDAR Tiles DTM", "National LIDAR Programme DSM", \
                                          "National LIDAR Programme DTM", "National LIDAR Programme First Return DSM", \
                                          "National LIDAR Programme Point Cloud"')
    parser.add_argument('--year', type=str, nargs=1, default='latest', help='directory to store tiles')
    parser.add_argument('--all-years', action='store_true', help='download all available years between --year and latest')
    parser.add_argument('--open-browser', action='store_false', help='opne chrome instance i.e. do not run headless')
    parser.add_argument('--browser', type=str, default='chrome', help='opne chrome instance i.e. do not run headless')
    parser.add_argument('--verbose', action='store_true', help='print something')
    args = parser.parse_args()
    args.extent = args.extent[0]
    
    if args.verbose and args.print_only

    # temp directory
    args.tmp_d = tempfile.mkdtemp()
    args.tmp_n = str(uuid.uuid4())
    if args.verbose: print('tmp dir:', args.tmp_d)

    shp = gp.read_file(args.extent)
    
    if shp.area.values[0] > 10000 or num_vertics(shp) > 1000:
        if args.verbose: 'input geometry is large and or complex, tiling data.'
        tile_input(shp, args)
    else:
        
        with ZipFile(os.path.join(args.tmp_d, args.tmp_n + '.zip'), 'w') as zipObj: 
            [zipObj.write(f) for f in glob.glob(os.path.splitext(args.extent)[0] + '*')]
        
        if args.verbose: print('zip saved to:',  os.path.join(args.tmp_d, args.tmp_n + '.zip'))

        download_tile(os.path.join(args.tmp_d, tmp_n + '.zip'),
                      product=args.product,
                      headerless=args.open_browser,
                      browser=args.browser,
                      verbose=args.verbose)
    
    



