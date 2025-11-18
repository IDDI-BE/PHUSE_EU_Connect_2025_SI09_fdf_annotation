# Example use of fdf_annotations.py class to format the annotations provided in fdf format
# to specific standards (font, fontsize, font-weight, font color, border color, background color)


import fdf_annotations as fdfa       
from collections import defaultdict

# The fdf file provided in inputfdfpath can be extracted 
# from the DUMMY_aCRF_PHUSE_EU_CONNECT_2025_unformatted.pdf
# using Adobe Reader (Comments Pane > Export all to file > save as fdf )
# It is also provided on this github page
# Please provide the proper filepath of the fdf file below

inputfdfpath=r"C:\Users\dbaele\Downloads\CRF playground\DUMMY_aCRF_PHUSE_EU_CONNECT_2025_unformatted.fdf"

#Please provide the filepath where the updated fdf is to be saved
outputfdfpath=r"C:\Users\dbaele\Downloads\CRF playground\DUMMY_aCRF_PHUSE_EU_CONNECT_2025_formatted.fdf"

###########################################""
# Standards
# backgroundcoloroder defines the background color to be used within a single page
# standardrcstyle: fontsize 12, non-bold, Arial  (Used on both domain header nnotations and variable annotations)
# rcopenboldspan: added on top of standardrcstyle to allow for bold annotations in  domain header annotations
# rccloseboldspan: closing tag associated with rcopenboldspan
# nonboldds, boldds: default /DS string for non-bold vs bold annotations
# nonboldda, boldda: default /DA string for non-bold vs bold annotations
###########################################""

backgroundcolororder=['191 255 255', '255 255 150', '150 255 150', '255 190 155',     #only first 4 colors defined in SDTM-MSG MSG V2.0
                    '0 146 146', '182 109 255', '219 109 0', '255 109 182', '0 109 219', '36 255 36', '255 182 219', '109 182 255'] #extra color order defined when needed
standardrcstyle={'font-size':'12.0pt', 'text-align':'left', 'color':'#000000', 'font-weight': 'normal', 'font-style': 'normal', 'font-family':'Arial', 'font-stretch':'normal'}
rcopenboldspan='<span style="font-weight:bold">'
rccloseboldspan='</span>'
nonboldds='font: Arial,sans-serif 12.0pt; text-align:left; color:#000000 '        #DS defines font color
boldds='font: bold Arial,sans-serif 12.0pt; text-align:left; color:#000000 '      #DS defines font color
nonboldda='0 0 0 rg /Arial 12 Tf'              #DA defines border color
boldda='0 0 0 rg /Arial,Bold 12 Tf'            #DA defines border color


###########################################
# Process annotations
###########################################

#import fdf

annots=fdfa.fdf_annotations(inputfdfpath)

#loop over all annotations to set /DA, /DS, /RC and harvest background colors used
color_dict=defaultdict(dict)    #will be used to translate background colors to expected background color
for annot in annots:
    if annots.hascontent(annot):
        #set /RC default style since applicable to both non-bold and bold annotations
        rcstring=annots.getrccontent(annot)
        rcstring=annots.removercreturns(rcstring)
        rcstring=annots.rc_dropspans(rcstring)
        rcstyles=annots.getrcstyles(rcstring)
        rcstyles=annots.rcstyles_setmasterstyle(rcstyles, standardrcstyle)
        rcstring=annots.rcstyles_to_rccontentstring(rcstyles)
        if annots.qualifyasheaderMSGV2(annot):
            #Set to bold in /RC tag using bold span
            rcstring=annots.rc_insertspan(rcstring, rcopenboldspan, rccloseboldspan)
            annots.updaterccontent(annot, rcstring)   #updating the actual /RC attrbibute here -- DO NOT FORGET
            #Set bold /DA and /DS
            annots.updatedacontent(annot, boldda)
            annots.updatedscontent(annot, boldds)   
        else:
            annots.updaterccontent(annot, rcstring)   #updating the actual /RC attrbibute here -- DO NOT FORGET
            #Set non-bold /DA and /DS
            annots.updatedacontent(annot, nonboldda)
            annots.updatedscontent(annot, nonboldds)
        # obtain the color_dict keys
        color_dict[annots.getpagenum(annot)][annots.rgb_fractoint(annots.getc(annot))]=""

#translate color_dict to expected color sequence: populate the color_dict with replacement values
for page, value in color_dict.items():
    for i, intcolor in enumerate(value):
        color_dict[page][intcolor]=backgroundcolororder[i]


#change backgroundcolor in annotations using color_dict populated above
for annot in annots:
    if annots.hasc(annot):
        page=annots.getpagenum(annot)
        keycolor=annots.rgb_fractoint(annots.getc(annot))
        updatedcolor=annots.rgb_c_inttofrac(color_dict[page][keycolor])
        annots.setc(annot, updatedcolor)

#Export updated fdf
annots.exportfdf(outputfdfpath, "N", "Y", "Y")
