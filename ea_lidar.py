import os
import uuid
import shutil
import glob
import time
import tempfile
import geopandas as gp
import numpy as np
from zipfile import ZipFile
import argparse

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException, StaleElementReferenceException

import urllib.request
from tqdm.auto import tqdm


def download_tile(zipf, download=False, product_list=[], 
                  verbose=True, download_dir=False, headless=True,
                  browser='chrome', year='latest', resolution='smallest', all_years=False,
                  print_only=True):
    
    if browser == 'firefox':
        if verbose: print('using FIREFOX')
        from selenium.webdriver.firefox.options import Options
        # you may need to import these as well
#        from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
#        from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
        
        options = Options()
        options.headless = headless
        # you may need to set capabilities and location of binary
#         cap = DesiredCapabilities().FIREFOX
#         cap["marionette"] = True
#         binary = FirefoxBinary('/Users/phil/anaconda2/envs/networkx/bin/firefox')
#         driver = webdriver.Firefox(executable_path='/Users/phil/anaconda2/envs/networkx/bin/geckodriver',
#                                    capabilities=cap,
#                                    firefox_binary=binary)
        driver = webdriver.Firefox(options=options)
    else:
        if verbose: print('using CHROME')
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        import chromedriver_binary
        
        options = Options()
        options.headless = headless
        #driver = webdriver.Chrome(chromedriver_binary.chromedriver_filename, options=options)
        #driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver = webdriver.Chrome(executable_path=r'C:/Users/ee21ess/OneDrive - University of Leeds/Placement/chromedriver-win64/chromedriver-win64/chromedriver.exe')

    if verbose: print('...waiting for page to load')
    #driver.get("https://environment.data.gov.uk/DefraDataDownload/?Mode=survey")
    driver.get("https://environment.data.gov.uk/survey")
    wait = WebDriverWait(driver, 300)

    # select upload files from drop down list
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.src__StyledSelect-sc-sgud4a-0.caJfrq")))
    dropdown = Select(driver.find_element(By.CSS_SELECTOR,"select.src__StyledSelect-sc-sgud4a-0.caJfrq"))
    dropdown.select_by_visible_text('Upload shapefile')

    if verbose: print('...waiting for shapefile to load')
    # upload files
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.src__StyledInput-sc-176u3do-0.koUZzt")))
    driver.find_element(by=By.CSS_SELECTOR, value="input.src__StyledInput-sc-176u3do-0.koUZzt").send_keys([zipf])

   
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.src__StyledButton-sc-19ocyxv-0.gRWgCC.download-button")))
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.src__StyledButton-sc-19ocyxv-0.gRWgCC.download-button")))
#    try:
#        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".grid-item-container")))
#    except TimeoutException:
#        if driver.find_element_by_css_selector( 'div.errorsContainer:nth-child(1)').is_displayed():
#            raise Exception("The AOI Polygon uploaded exceeds the maximum number of vertices allowed. Use a less complex polygon The maximum vertex count is : 1000")
    E1 = driver.find_element(by=By.CSS_SELECTOR, value="button.src__StyledButton-sc-19ocyxv-0.gRWgCC.download-button")

    if verbose: print('...waiting for available products to load') 
    while True: # hack :(
        try:
            E1.click()
        except StaleElementReferenceException as e:
            break

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.sc-6d83a994-0.fswiLB")))
    products = [x.get_attribute('value') for x in 
                 Select(driver.find_element(by=By.CSS_SELECTOR, value="select.src__StyledSelect-sc-sgud4a-0.caJfrq")).options]
    print(products)

    
    for product in product_list:
        if product not in products:
            print(f'product {product} not available')
        else:
            xP = "option[value='{}']".format(product)#(products.index(product) + 1)
            #xP = "option[value='lidar_point_cloud']"
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, xP)))
            driver.find_element(by=By.CSS_SELECTOR, value=xP).click()

            years = [x.get_attribute('value') for x in Select(driver.find_elements(by=By.CSS_SELECTOR, value='select.src__StyledSelect-sc-sgud4a-0.caJfrq')[1]).options]
            print(years)
            if year == 'latest':
                #xY = ['//*[@id="yearSelect"]/option[1]']
                xY = ["option[value='{}']".format(years[0])] 
                if verbose: print('downloading data for: {}'.format(years[0]))
            elif not all_years:
                if year not in years: 
                    print('no {} data available for {}, available years are {}'.format(product, year, ', '.join(years)))
                    continue
#                     raise YearError('Years available are {}'.format(years))
                xY = ["option[value='{}']".format(year)]
            else:
                most_recent = int(years[0])
                if most_recent < int(year): 
#                     raise YearError('Years available are {}'.format(years))
                    print('no {} data available for {}, available years are {}'.format(product, year, ', '.join(years)))
                    continue
                available_years = [str(y) for y in range(int(year), most_recent + 1) if str(y) in years]
                xY = ["option[value='{}']".format(y) for y in available_years]

    
            for xYs in xY:
                #current = years[int(xYs.split(',')[-1][:-1]) - 1]
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, xYs)))
                driver.find_element(by=By.CSS_SELECTOR, value=xYs).click()
                current = driver.find_element(by=By.CSS_SELECTOR, value=xYs).text

                # select resolution
                
                res_m = [x.get_attribute('value') for x in Select(driver.find_elements(by=By.CSS_SELECTOR, value='select.src__StyledSelect-sc-sgud4a-0.caJfrq')[2]).options]
                print(res_m)
                res = [float(r) for r in res_m]

                if np.isnan(res[0]):
                    if verbose: print('no resolution selection available')
                    r = ''
                
                else:
                    # smallest
                    if resolution == 'smallest':
                        r = np.min(res)
                        if r< 1:
                            r = f'{r}m'
                        else:
                            r = f'{int(r)}m'

                    # biggest
                    elif resolution == 'biggest':
                        r = np.max(res)
                        if r< 1:
                            r = f'{r}m'
                        else:
                            r = f'{int(r)}m'

                    # specified
                    else:
                        if float(resolution) not in res: 
                            print('no {} data available in {}m resolution, available resolutions are {}'.format(product, resolution, ', '.join([r + 'm' for r in res_m])))
                            continue
                        r = f'{resolution}m'

                    if verbose: print(f'Selected {r} resolution')
                    xR = "option[value='{}']".format(r[:-1])
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, xR)))
                    driver.find_element(by=By.CSS_SELECTOR, value=xR).click()
                

                linki = 1
                while linki > 0:
                    try:
                        # href = driver.find_element(by=By.CSS_SELECTOR, value='.data-ready-container > a:nth-child({})'.format(linki)).get_attribute("href")
                        href = driver.find_element(by=By.CSS_SELECTOR, value="a#link-{}.src__Link-sc-1loawqx-0.bYULlK".format(linki-1)).get_attribute("href")
                        file_loc = os.path.join(os.path.split(zipf[0])[0] if not download_dir else download_dir, product, href.split('/')[-1].split('?')[0] + f'_{current}_{r}.zip') 
                        if print_only: 
                            print('available:', href)
                        else:
                            if download_dir and not os.path.exists(os.path.join(download_dir, product)):
                                os.makedirs(os.path.join(download_dir, product))
                            if not os.path.isfile(file_loc): 
                                download_url(href, file_loc)
                                if verbose: print('saved to:', file_loc)

                        linki += 1
                    except NoSuchElementException:
                        if verbose and not print_only: print(linki - 1, 'files downloaded for {}'.format(current))
                        linki = -1
                    except Exception as err:
                        print(err)
                
    return driver
                
                
class DownloadProgressBar(tqdm):
    
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)
        

def download_url(url, output_path):
    
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1].split('?')[0]) as t:
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

class YearError(Exception):
    pass

def tile_input(shp, args):
    
    osgb = gp.read_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'shp', 'OSGB_Grid_5km.shp'))
    osgb_sindex = osgb.sindex
    tile_index = [list(osgb_sindex.intersection(row.geometry.bounds)) for row in shp.itertuples()][0]
    for idx in tile_index:
        tmp_shp = gp.GeoDataFrame(geometry=[osgb.loc[idx].geometry], crs='EPSG:27700')
        if tmp_shp.intersects(shp).values[0]:
            tile_tmp = os.path.join(args.tmp_d, '{}_{}'.format(args.tmp_n, idx))
            gp.GeoDataFrame(geometry=[osgb.loc[idx].geometry]).to_file(tile_tmp + '.shp')
            with ZipFile(os.path.join(args.tmp_d, tile_tmp + '.zip'), 'w') as zipObj: 
                [zipObj.write(f) for f in glob.glob(tile_tmp + '*')]
            if args.verbose: print('zip file saved to:', os.path.join(args.tmp_d, tile_tmp + '.zip'))	
            driver = download_tile(tile_tmp + '.zip',
                                   print_only=args.print_only,
                                   product_list=args.required_products,
                                   headless=True,
                                   year=args.year,
                                   all_years=args.all_years,
                                   download_dir=args.odir,
                                   browser=args.browser,
                                   verbose=args.verbose)
            if not args.open_browser: driver.close()
            #break
            
    
def main(args):
    if args.odir: args.odir = os.path.abspath(args.odir)

    #products = ["LIDAR Tiles DSM", "LIDAR Tiles DTM", "LIDAR Point Cloud", "National LIDAR Programme Point Cloud"]
    products = ["lidar_tiles_dsm", "lidar_tiles_dtm", "lidar_point_cloud", "national_lidar_programme_point_cloud"]
    args.required_products = [p for (p, b) in zip(products, [args.dsm, args.dtm, args.point_cloud, args.national]) if b]
    if not any(args.required_products):
        raise Exception('pick one or more products using the --point-cloud, --dsm or --dtm flags')   
 
    if args.verbose and args.print_only: print('PRINT ONLY - no data will be downloaded')

    # temp directory
    args.tmp_d = tempfile.mkdtemp()
    args.tmp_n = str(uuid.uuid4())

    shp = gp.read_file(args.extent)
    
    if shp.area.values[0] > 561333677 or len(shp.explode(index_parts=True)) > 1:        
        if args.verbose: 'input geometry is large and or complex, tiling data.'
        tile_input(shp, args)

    if num_vertices(shp) > 1000: # maximum number of vertics accepted by application
        if args.verbose: print('simplifying to <1000 vertices') 
        simp = 10
    
        while num_vertices(shp) > 1000:
            shp.geometry = shp.simplify(simp)
            simp *= 2

        shp.to_file(os.path.join(args.tmp_d, args.tmp_n + '.shp'))
        args.extent = os.path.join(args.tmp_d, args.tmp_n + '.shp')
        if args.verbose: print('simplified polygon saved to:', os.path.join(args.tmp_d, args.tmp_n + '.shp'))    

    zipPath = os.path.join(args.odir, args.tmp_n + '.zip') 
    with ZipFile(zipPath, 'w') as zipObj: 
        [zipObj.write(f, os.path.basename(f)) for f in glob.glob(os.path.splitext(args.extent)[0] + '*') if not f.endswith('.zip')]
        #[print(f) for f in glob.glob(os.path.splitext(args.extent)[0] + '*') if not f.endswith('.zip')]

    if args.verbose: print('zip file saved to:', zipPath)

    driver = download_tile(zipPath,
                           print_only=args.print_only,
                           year=args.year,
                           all_years=args.all_years,
                           resolution=args.resolution,
                           product_list=args.required_products,
                           download_dir=args.odir,
                           headless=args.open_browser,
                           browser=args.browser,
                           verbose=args.verbose)

    os.unlink(zipPath)
    print('temp zip file deleted')

    if not args.open_browser: driver.close()
    
    
if __name__ == '__main__':
   
    # some arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('extent', type=str, help='path to extent')
    parser.add_argument('--print-only', action='store_true', help='print list of available data')
    parser.add_argument('--odir', default='.', help='directory to store tiles')
    parser.add_argument('--year', type=str, default='latest', help='specify year data captured')
    parser.add_argument('--resolution', type=str, default='smallest', help='specify resolution of data')
    parser.add_argument('--all-years', action='store_true', help='download all available years between --year and latest')
    parser.add_argument('--open-browser', action='store_false', help='open browser i.e. do not run headless')
    parser.add_argument('--browser', type=str, default='chrome', help='choose between chrome and firefox')
    parser.add_argument('--verbose', action='store_true', help='print something')
    
#     parser.add_argument('--product', '-p', type=str, default='LIDAR Composite DTM',
#                         help='choose from "LIDAR Composite DSM", "LIDAR Composite DTM", \
#                                           "LIDAR Point Cloud", "LIDAR Tiles DSM", \
#                                           "LIDAR Tiles DTM", "National LIDAR Programme DSM", \
#                                           "National LIDAR Programme DTM", "National LIDAR Programme First Return DSM", \
#                                           "National LIDAR Programme Point Cloud"')
    parser.add_argument('--point-cloud', '-pc', action='store_true', help='download point cloud')
    parser.add_argument('--national', action='store_true', help='download point cloud')
    parser.add_argument('--dsm', action='store_true', help='download dsm')
    parser.add_argument('--dtm', action='store_true', help='download dtm')
    
    args = parser.parse_args()

    main(args)
    