import re
import io

class fdf_annotations:
    """
    Class that facilitates FDF import, manipulation and export of annotations.
    The intended use is for CDISC SDTM annotations that need to be made compliant with CDISC SDTM-MSG V2.0 guidelines.
    This class is the underlying code developed for the paper and presentation of PHUSE EU Connect 2025 SI09 "Add More MSG to Your Annotations" (19NOV2025) in Hamburg.

    Author of code: Davy Baele, Team Leader CDM Programming, IDDI

    ------------------------------------------------------------------------------------------------------------------

    The __init__ method should be used to load an FDF file exported from an SDTM acrf.pdf using Adobe Reader 2025.x.y.
    It allows for updating annotation formatting (fonts, colors, ...) within freetext (or other) annotation objects.
    
    The class is designed to be extended by additional methods easily. It only consists of a handful of lists and dictionaries within an object that contain the information contained within the FDF file:
    
    * ordered_fdf_key is a list containing the chronologically encountered object identifier (header, ..., trailer).
    * root_key is a list containing the object references included in the root object. This should be seen as an annotations inventory embedded within the FDF file.
    * fdf_dict is the central dictionary containing the object identifier of each annotation object as key, and the value the full FDF string contained within that object.
    * bs_subobject dict is a dictionary containing all annotation objects that have their border style defined in another object referenced from it. The latter object is not included in the root_key list.
    * popup_subobject_dict and parent_subobject_dict contain references towards each other. Typically the information to define a line, arrow, ... is spread around these 2 objects Both objects are typically referenced from within the root_key list.
     
    The majority of the methods provided use regular expressions to obtain/update the required parameters of interest.
    Additional methods of interest can easily be added accordingly to obtain and manipulate the desired information contained in the dictionaries and lists.      
    
    """
    root_key=[]                #list containing all objects referenced from the root catalog object
    ordered_fdf_key=[]
    fdf_dict={}
    bs_subobject_dict={}       #border style subobject references - referenced objects not included in root_key
    popup_subobject_dict={}    #popup style subobject references - referenced objects included in root_key
    parent_subobject_dict={}   #parent style subobject references - referenced objects included in root_key
    interobjectcounter=0
    
    def __init__(self, inputfdfpath: str) -> None:
        """
        Method to load an FDF file into the fdf_annotations class. The FDF file is assumed to be obtained by exporting comments from an existing SDTM acrf.pdf in Adobe Reader 2025.x.y.

        Input: inputfdfpath (str): string containing the path to an fdf file that is to be loaded.
        Output: fdf_annotations object containing the provided FDF file contents.
        Return: None.         
        """

        #load input fdf        
        with open(inputfdfpath, "r", encoding='windows-1252') as file:
            input_fdf_content=file.read()
        
        #obtain header from input fdf   [header: everything until first object identifier (in lookahead)]
        headerendtag=r"\n(?=\d+ \d+ obj\n)"
        headerend=re.search(headerendtag, input_fdf_content)    
        headertext=input_fdf_content[0:headerend.span()[0]]    
        self.fdf_dict["header"]=headertext
        self.ordered_fdf_key.append("header")    
        toprocess=input_fdf_content[headerend.span()[1]:]    
        #obtain individual objects - loop per object
        objectidtag=r"\d+ \d+ obj(?=\n)"
        objectendtag=r"endobj(?=\n)"
        objectid=re.search(objectidtag, toprocess)    
        while objectid!=None:        
            objectidstart=objectid.span()[0]
            if objectidstart !=0:
                self.fdf_dict[f"interobj{str(self.interobjectcounter)}"]=toprocess[0:objectidstart]
                self.ordered_fdf_key.append(f"interobj{str(self.interobjectcounter)}")
                self.interobjectcounter+=1
            objectend=re.search(objectendtag, toprocess)
        
            objectkey=toprocess[objectidstart:objectid.span()[1]]        
            self.fdf_dict[objectkey]=toprocess[objectid.span()[1]+1:objectend.span()[1]]        
            self.ordered_fdf_key.append(objectkey)
            # prepare for next iteration
            toprocess=toprocess[objectend.span()[1]+1:]
            objectid=re.search(objectidtag, toprocess)    
        #obtain trailer = everything left below last annotation object
        self.fdf_dict["trailer"]=toprocess
        self.ordered_fdf_key.append("trailer")
        toprocess=""

        #populate root_key list with referenced annotations object IDs:  (inventory object = 2nd item in ordered_fdf_key)
        inventoryobjtext=self.fdf_dict[self.ordered_fdf_key[1]]
        inventorytag="/Annots\[((\d+ \d+ R )*(\d+ \d+ R))\]"
        inventorymatch=re.search(inventorytag, inventoryobjtext)
        if inventorymatch:
            inventory_toprocess=inventorymatch.group(1)
            individualreftag="\d+ \d+ R"
            while inventory_toprocess:                
                individualrefmatch=re.search(individualreftag, inventory_toprocess)
                if individualrefmatch:
                    self.root_key.append(inventory_toprocess[individualrefmatch.span()[0]:individualrefmatch.span()[1]])
                    inventory_toprocess=inventory_toprocess[individualrefmatch.span()[1]+1:].strip()
                else:
                    print(f"Unanticipated residual string encountered within root object provided: {inventory_toprocess}")
                    self.root_key.append(inventory_toprocess)
                    inventory_toprocess=""            
        else:
            print(f"No referenced annotation blocks found within the inventory root object within the privded fdf file {inputfdfpath}.")
            
        #populate subobject_dicts i.e. objects referenced from a parent object (excluding the inventory root object)
        referencetag="(/BS|/Popup|/Parent|/[^/]+) (\d+ \d+ R)"
        for item in self.ordered_fdf_key[2:]:         #activiely excluding header and catalog object   
            annotcontent=self.fdf_dict[item]            
            referencematch=re.search(referencetag, annotcontent)            
            if referencematch and item !="trailer":      #actively excluding trailer object
                if referencematch.group(1)=="/BS":
                    self.bs_subobject_dict[item]=referencematch.group(2)
                elif referencematch.group(1)=="/Popup":
                    self.parent_subobject_dict[item]=referencematch.group(2)
                elif referencematch.group(1)=="/Parent":
                    self.parent_subobject_dict[item]=referencematch.group(2)
                else:
                    print(f"Unanticipated subobject reference detected in content of annotation object (ID={item}): Deleting dependent objects might cause undesired results.")


    def __iter__(self):
        """"
        Iterate over elements present in ordered_fdf_key, i.e. the object IDs included in an fdf_annotation object.
        """
        return iter(self.ordered_fdf_key)
    
    
    def getannotation(self, objectid) -> str:
        """
        Method that returns the annotation value for the provided annotation id. Note that annotation value refers to the full object.
        If the provided object id value is not existing in the fdf_dict it will return None.

        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: string value containing the value of the annotation stored in the fdf_dict for the provided objectid key.
        """

        if objectid in self.fdf_dict:
            return self.fdf_dict[objectid]
        else: 
            return None

    def __getitem__(self, objectid: str):
        """
        Method that calls the getannotation method.
        """
        return self.getannotation(self, objectid)
    

    def getcontent(self, objectid: str) -> str:
        """
        Method that returns the value of the /Contents tag for the provided annotation id (objectid).

        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: (str) String containing the value of the /Contents attribute.
                None is returned in case the provided objectid is not included in fdf_dict, or if the /Contents tag is not properly opened or closed.
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            annotstring=self.fdf_dict[objectid]
            contenttagstart=r"(?<!\\)(/Contents\()"
            contenttagend=r"(?<!\\)(\))"
            contentstartmatch=re.search(contenttagstart, annotstring)
            if contentstartmatch:
                toprocess=annotstring[contentstartmatch.end(1):]
                contentendmatch=re.search(contenttagend, toprocess)
                if contentendmatch:
                    return toprocess[:contentendmatch.start(1)]

            print(f"No proper opening and closing of /Contents tag found in provided object {objectid}.")
            return None


    def getrccontent(self, objectid) -> str:
        """
        Method that returns the /RC attribute value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: (str) String containing the value of the /RC tag.
                None is returned in case the provided objectid is not included in fdf_dict, or if the /RC tag is not properly opened or closed.
        """   

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            annotstring=self.fdf_dict[objectid]
            rcstarttag=r"(?<!\\)/RC\("
            rcstartmatch=re.search(rcstarttag, annotstring)
            if rcstartmatch:                
                toprocess=annotstring[rcstartmatch.end():]
                rcendtag=r"(?<!\\)\)"
                rcendmatch=re.search(rcendtag, toprocess)
                if rcendmatch:
                    return toprocess[0:rcendmatch.start()]
                else:
                    print(f"No /RC closing parenthesis found for provided object {objectid}.")
                    return None
            else:
                print(f"No /RC opening tag found in provided object {objectid}.")
                return None

    def getdscontent(self, objectid) -> str:
        """
        Method that returns the /DS attibute value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: (str) String containing the value of the /DS tag as second element. 
                None is returned in case the provided objectid is not included in fdf_dict, or if the /DS tag is not properly opened or closed.          
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:            
            annotstring=self.fdf_dict[objectid]
            dsstarttag=r"(?<!\\)/DS\("
            dsstartmatch=re.search(dsstarttag, annotstring)
            if dsstartmatch:                
                toprocess=annotstring[dsstartmatch.end():]
                dsendtag=r"(?<!\\)\)"
                dsendmatch=re.search(dsendtag, toprocess)
                if dsendmatch:
                    return toprocess[0:dsendmatch.start()]
                else:
                    print(f"No /DS closing parenthesis found for provided object {objectid}.")
                    return None
            else:
                print(f"No /DS opening tag found in provided object {objectid}.")
                return None
    
    def getdacontent(self, objectid) -> str:
        """
        Method that returns the /DA attibute value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: (str) String containing the value of the /DA tag as second element. 
                None is returned in case the provided objectid is not included in fdf_dict, or if the /DA tag is not properly opened or closed.        
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            annotstring=self.fdf_dict[objectid]
            dastarttag=r"(?<!\\)/DA\("
            dastartmatch=re.search(dastarttag, annotstring)
            if dastartmatch:                
                toprocess=annotstring[dastartmatch.end():]
                daendtag=r"(?<!\\)\)"
                daendmatch=re.search(daendtag, toprocess)
                if daendmatch:
                    return toprocess[0:daendmatch.start()]                    
                else:
                    print(f"No /DA closing parenthesis found for provided object {objectid}.")
                    return None
            else:
                print(f"No /DA opening tag found in provided object {objectid}.")
                return None

    

    def updaterccontent(self, objectid: str, updatedrcstring: str) -> None:
        """
        Method that updates the /RC attribute value contained within the annotation ID.
        No update is performed if no /RC tag is contained within the annotation - note that the RC tag must have a proper opening and closing parenthesis to be qualified as present.
        Note: This method calls the addrcreturns method to split the provided updatedrcstring in chunks of 255 chars ending with a backslash followed by a new line.
        
        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            updatedrcstring (str): updated string that will replace the /RC contents within the annotation object.
        Return: None.
        
        """

        
        if objectid in self.fdf_dict:
            rclist=[]
            annotstring=self.fdf_dict[objectid]
            rcstarttag=r"(?<!\\)/RC\("
            rcstartmatch=re.search(rcstarttag, annotstring)
            if rcstartmatch:          #/RC start found      
                rclist.append(annotstring[0:rcstartmatch.end()])     #add contents prior to /RC contents to list (not to be touched by this method)
                toprocess=annotstring[rcstartmatch.end():]
                rcendtag=r"(?<!\\)\)"
                rcendmatch=re.search(rcendtag, toprocess)
                if rcendmatch:  #/RC end found
                    rclist.append(fdf_annotations.addrcreturns(updatedrcstring))              #part to be replaced by the updated rc string that contains carriage returns as per FDF requirements
                    rclist.append(toprocess[rcendmatch.start():])               #part following the /RC contents (not to be touched by this method)
                    self.fdf_dict[objectid]=rclist[0]+rclist[1]+rclist[2]       #update annotation value in fdf_dict

                else:
                    print(f"No /RC closing parenthesis found for provided object {objectid}.")
                
            else:
                print(f"No /RC opening tag found in provided object {objectid}.")
               
    def updatedscontent(self, objectid: str, updateddsstring: str) -> None:
        """
        Method that updates the /DS attribute value contained within the annotation ID.
        No update is performed if no /DS tag is contained within the annotation - note that the DS tag must have a proper opening and closing parenthesis to be qualified as present.
          
        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            updateddsstring (str): Updated string that will replace the /DS contents within the annotation object.
        Return: None. 

        """

        
        if objectid in self.fdf_dict:
            dslist=[]
            annotstring=self.fdf_dict[objectid]
            dsstarttag=r"(?<!\\)/DS\("
            dsstartmatch=re.search(dsstarttag, annotstring)
            if dsstartmatch:          #/DS start found      
                dslist.append(annotstring[0:dsstartmatch.end()])     #add contents prior to /DS contents to list (not to be touched by this method)
                toprocess=annotstring[dsstartmatch.end():]
                dsendtag=r"(?<!\\)\)"
                dsendmatch=re.search(dsendtag, toprocess)
                if dsendmatch:  #/DS end found
                    dslist.append(updateddsstring)              #part to be replaced by the updated DS string that contains carriage returns as per FDF requirements
                    dslist.append(toprocess[dsendmatch.start():])               #part following the /DS contents (not to be touched by this method)
                    self.fdf_dict[objectid]=dslist[0]+dslist[1]+dslist[2]       #update annotation value in fdf_dict

                else:
                    print(f"No /DS closing parenthesis found for provided object {objectid}.")
                
            else:
                print(f"No /DS opening tag found in provided object {objectid}.")

    def updatedacontent(self, objectid: str, updateddastring: str) -> None:
        """
        Method that updates the /DA attribute value contained within the annotation ID.
        No update is performed if no /DA tag is contained within the annotation - note that the DA tag must have a proper opening and closing parenthesis to be qualified as present.
          
        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            updateddastring (str): Updated string that will replace the /DA contents within the annotation object
        Return: None.
        
        """

        
        if objectid in self.fdf_dict:
            dalist=[]
            annotstring=self.fdf_dict[objectid]
            dastarttag=r"(?<!\\)/DA\("
            dastartmatch=re.search(dastarttag, annotstring)
            if dastartmatch:          #/DA start found      
                dalist.append(annotstring[0:dastartmatch.end()])     #add contents prior to /DA contents to list (not to be touched by this method)
                toprocess=annotstring[dastartmatch.end():]
                daendtag=r"(?<!\\)\)"
                daendmatch=re.search(daendtag, toprocess)
                if daendmatch:  #/DA end found
                    dalist.append(updateddastring)              #part to be replaced by the updated DA string that contains carriage returns as per FDF requirements
                    dalist.append(toprocess[daendmatch.start():])               #part following the /DA contents (not to be touched by this method)
                    self.fdf_dict[objectid]=dalist[0]+dalist[1]+dalist[2]       #update annotation value in fdf_dict

                else:
                    print(f"No /DA closing parenthesis found for provided object {objectid}.")
                
            else:
                print(f"No /DA opening tag found in provided object {objectid}.")
   
    def getpagenum(self, objectid: str) -> int:
        """
        Method that returns the page number contained within the /Page attribute. Note this value is zero-based.

        Input: objectid (str): String value containing the object identifier for the annotation.            
        Return:
            int containing the page number.
            None is returned in case the provided objectid is not included in fdf_dict, or if the /Page tag is not existing.   
        
        """    
        if objectid in self.fdf_dict:
            pagetag=r"/Page (\d+)(?=/)"
            pagematch=re.search(pagetag, self.fdf_dict[objectid])            
            if pagematch:
                return int(pagematch.group(1))  
            print(f"The provided object (ID= {objectid}) has no page attribute.")
        else:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")            
        return None
    
        
    def setpagenum(self, objectid: str, pagenum: int) -> None:
        """
        Method that sets the page number contained within the /Page attribute. Note this value is zero-based.

        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            pagenum (int): integer value containing the zero-based page number to be set for the provided objectid.            
        Return: None.        
        """    
        if objectid in self.fdf_dict:
            pagetag=r"/Page (\d+)(?=/)"
            pagematch=re.search(pagetag, self.fdf_dict[objectid])            
            if pagematch:
                pretagtext=self.fdf_dict[objectid][0:pagematch.span()[0]]
                tagtext=f"/Page {pagenum}"
                posttagtext=self.fdf_dict[objectid][pagematch.span()[1]:]
                self.fdf_dict[objectid]=pretagtext+tagtext+posttagtext
            else:
                print(f"The provided object(ID= {objectid}) has no page attribute to set.")
        else:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")

    
    def getrect(self, objectid: str) -> str:
        """
        Method that returns the /Rect attribute value as a string for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /Rect attribute it will return None.
        
        Input: objectid (str): String value containing the object identifier for the annotation.  
        Return: (str) String containing the /Rect value enclosed in square brackets.
                None is returned in case the provided objectid is not included in fdf_dict, or if the /Rect tag is not existing.
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        recttag=r"(?<!\\)/Rect(\[.*?\])"
        rectmatch=re.search(recttag, self.fdf_dict[objectid])
        if rectmatch:                        
            return str(rectmatch.group(1)) 
        print(f"The provided object (ID= {objectid}) has no /Rect attribute.") 
        return None


    def setrect(self, objectid: str, rectstring: str) -> None:
        """
        Method that updates the /Rect value with the provided rectstring value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /Rect attribute it will return None.
        
        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            rectstring: string: value that will be assigned to the /Rect tag. Note: the provided value should be encapsulated within square brackets.
        Return: None.
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        recttag=r"(?<!\\)/Rect(\[.*?\])"         
        rectmatch=re.search(recttag, self.fdf_dict[objectid])
        if rectmatch:
            pretagtext=self.fdf_dict[objectid][0:rectmatch.span()[0]]
            tagtext=f"/Rect{rectstring}"
            posttagtext=self.fdf_dict[objectid][rectmatch.span()[1]:]
            self.fdf_dict[objectid]=pretagtext+tagtext+posttagtext
            return None
        print(f"The provided object (ID= {objectid}) has no /Rect attribute.") 
        return None
    
    def getc(self, objectid: str) -> str:
        """
        Method that returns the /C value as a string for the provided annotation id. 
        This value represents the background fill within an annotation box within Text Box Comments. 
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /C attribute it will return None.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: (str) String containing the /C value enclosed in square brackets.
                None is returned in case the provided objectid is not included in fdf_dict, or if the /C tag is not existing.
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        ctag=r"(?<!\\)/C(\[.*?\])"
        cmatch=re.search(ctag, self.fdf_dict[objectid])
        if cmatch:                        
            return str(cmatch.group(1)) 
        print(f"The provided object (ID= {objectid}) has no /C attribute.") 
        return None

    def setc(self, objectid: str, cstring: str) -> None:
        """
        Method that updates the /C value with the provided cstring value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /C attribute it will return None.
        
        Input: 
            objectid (str): String value containing the object identifier for the annotation.
            cstring (str): String value that will be assigned to the /C tag. Note: the provided value should be encapsulated within square brackets.
        Return: None
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        ctag=r"(?<!\\)/C(\[.*?\])"         
        cmatch=re.search(ctag, self.fdf_dict[objectid])
        if cmatch:
            pretagtext=self.fdf_dict[objectid][0:cmatch.span()[0]]
            tagtext=f"/C{cstring}"
            posttagtext=self.fdf_dict[objectid][cmatch.span()[1]:]
            self.fdf_dict[objectid]=pretagtext+tagtext+posttagtext
            return None                   
        print(f"The provided object (ID= {objectid}) has no /C attribute.") 
        return None


    def removefromroot(self, objectid: str) -> None:
        """
        Method that removes the provided objectid from the root_key list. I.e. It removes the reference from the catalog object, while not touching ordered_fdf_key list.

        Input: objectid (str): Object identifier:  "\d+ \d+ obj" or "\d+ \d+ R".
        Output: None.
        """ 
        objecttag2=r"^(\d+ \d+ )obj$"    #needed to reroute "\d+ \d+ obj" objects towards "\d+ \d+ R" values present in the key        
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:             #reroute spelling of object referenced
            objectid=objecttag2match.group(1)+"R"
        if objectid in self.root_key:
            self.root_key=[object for object in self.root_key if object != objectid]    #ensure all references are removed: list comprehension
        else:
            print(f"The provided object (ID= {objectid}) was not part of the root catalog object.")


    def addtoroot(self, objectid: str, insertposition: int) -> None:         
        """
        Method that adds a provided objectid to the root catalog object list (root_key) at the provided position within he list.

        The method will only treat provided objectid values of the following format: "\d+ \d+ R" or "\d+ \d+ obj", E.g., "16 0 R" or "17 0 obj"

        Input Arguments:
            objectid (str): Object identifier to be inserted into the root catalog object list  (root_key).
            insertposition (int): Index position where the provided objectid is to be inserted into the root catalog object list (root_key).
                A value of -1 means that the object will be inserted in the last position in the root catalog object list (root_key).
        Return: None.
        
        """
        
        
        #value of -1 ensures object is added as last element to the list (via append iso insert)
        objecttag=r"^\d+ \d+ R$"
        objecttag2=r"^(\d+ \d+ )obj$"
        objecttagmatch=re.search(objecttag, objectid)
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:
            objectid=objecttag2match.group(1)+"R"
        if objecttagmatch or objecttag2match:
            if insertposition != -1:       #insert using position -1 yields element included at 2nd last place - not desired and hence bypassed by append method 
                self.root_key.insert(insertposition, objectid)
            else:                        #ensuring -1 is truely last element added to the list
                self.root_key.append(objectid)
        else:
            print(f"The provided object (ID= {objectid}) was not added to the root catalog as it didn't meet formatting requirements.")


    def rebuildrootkey(self) -> None:
        """
        Method that rebuilds the root catalog object root_key by considering all objects present in the ordered_fdf_key list that are of the form "\d+ \d+ obj".
        The method is actively excluding the border style subannotations referenced by parent annotations (i.e. object identifiers resolved in the bs_subobject_dict) within the newly created root_key.
        The method considers the 2nd element in the ordered_fdf_key list as the root catalog object itself.
        Header and trailer and any other object not identified by "\d+ \d+ obj formatting within the ordered_fdf_key are not considered by this method.
        Note that this method does not update the rootvalue present in the fdf_dict. The latter is (to be) done during export of the object to fdf using method exportfdf.

        Input argument: None.
        Return: None.
        """
        
        self.root_key.clear()
        objecttag=r"^(\d+ \d+ )(R|obj)$"
        for objectid in self.ordered_fdf_key[2:len(self.ordered_fdf_key)]:
            objectid_R=""
            objectid_obj=""
            subobjectvalues=self.bs_subobject_dict.values()    #create list of referenced values of the dictionary for ease of lookup - since we're not interested in the key
            objecttagmatch=re.search(objecttag, objectid)
            if objecttagmatch:                    
                objectid_R=objecttagmatch.group(1)+"R"
                objectid_obj=objecttagmatch.group(1)+"obj" 
                if objectid_R not in subobjectvalues and objectid_obj not in subobjectvalues:
                    self.root_key.append(objectid_R)


    def updaterootvalue(self) -> None:
        """
        Method that takes the root_key list and recreates the value of the root catalog object within the fdf_dict accordingly.
        This method allows for properly (re-)exporting an updated fdf_annotations object to an fdf file.
        The method considers the 2nd element in the ordered_fdf_key list as the root catalog object itself.

        Input: None
        return: None        
        """
        rootcatalogID=self.ordered_fdf_key[1]    #obtain ID of root catalog object
        oldrootvalue=self.fdf_dict[rootcatalogID]        
        newcatalogref=" ".join(self.root_key)    #transform root_key to single line string value with space as separator


        inventorytag="/Annots\[((\d+ \d+ R )*(\d+ \d+ R))\]"
        inventorymatch=re.search(inventorytag, oldrootvalue)
        if inventorymatch:
            precatalogref=oldrootvalue[0:inventorymatch.span()[0]+8]            
            postcatalogref=oldrootvalue[inventorymatch.span()[1]-1:]           
            self.fdf_dict[rootcatalogID]=precatalogref+newcatalogref+postcatalogref
        else:
            print("Existing root value could not be updated due to unexpected structure - creating a generic one instead")
            precatalogref="<</FDF<</Annots["
            postcatalogref="]/F(/C/genericdoc.pdf)/UF(/C/generic.pdf)>>/Type/Catalog>>"
            self.fdf_dict[rootcatalogID]=precatalogref+newcatalogref+postcatalogref


    def updatetrailer(self) -> None:
        """
        Method that updates the trailer element in the fdf_dict, while also ensuring that trailer is present once as last item in the ordered_fdf_key list.
        The method ensures that the value of the reference inside the trailer object points to the object ID of the root catalog object.
        The method considers the 2nd element in the ordered_fdf_key list as the root catalog object itself.
        This method allows for properly (re-)exporting an updated fdf_annotations object to an fdf file.
        

        Input: None
        return: None        
        """
        rootcatalogID=self.ordered_fdf_key[1]    #obtain ID of root catalog object
        

        #ensure trailer is last element in list
        self.ordered_fdf_key = [item for item in self.ordered_fdf_key if item !="trailer"]       
        self.ordered_fdf_key.append("trailer")
        
        #verify existing trailer value
        recreate_trailer="Y"   #preseed to Y, only set to N if value passes checks
        #check if current trailer matches with root catalog object
        if self.ordered_fdf_key[-1] =="trailer":       
            trailertag=r"^trailer\s*\n?\r?<</Root (\d+ \d+ )R>>\s*\n?\r?\s*%%EOF"
            trailermatch=re.search(trailertag, self.fdf_dict["trailer"])
            if trailermatch:                
                if trailermatch.group(1)+"obj"==self.ordered_fdf_key[1]:
                    recreate_trailer="N"
        if recreate_trailer=="Y":
            catalogtag="^(\d+ \d+ )(R|obj)"
            catalogmatch=re.search(catalogtag, self.ordered_fdf_key[1])
            if catalogmatch:
                catalog_object_ref=catalogmatch.group(1)+"R"
                self.fdf_dict["trailer"]= "trailer\n<<" + catalog_object_ref +">>\n"+ r"%%EOF"
            else:
                print("No proper object catalog object ID found to allow for rebuilding trailer.")
                self.fdf_dict["trailer"]=""     #seed with empty value to not make pgm crash upon export

        
    def exportfdf(self, outputfdfpath: str, rebuild_key: str ="N", rebuild_value: str ="Y", rebuild_trailer: str="Y") -> None:
        """
        Method that exports the object to an fdf file specified in outputfdfpath.
        The additional arguments are optional to allow for rebuilding the root_key, root_value and trailer of the fdf_dict object.
        
        Inputs:
            outputfdfpath: (str) output path of the target fdf file the object should be exported to 
            rebuild_key = "Y"|"N": optional parameter to rebuild the root_catalog list internally - note this does not affect the output if rebuild_value is set to "N". Default is set to "N"
            rebuild_value="Y", "N": updates the fdf_dict value of the root catalog object according to the elements present in the root_key_list. Default is set to "Y"        
            rebuild_trailer ="Y", "N": updates the fdf_dict value of the trailer object to ensure alignment with the root catalog object ID and ensures it's included as the last item inside the ordered_fdf_key list. 
                Default Value is set to "Y"
        """
        
        if rebuild_key=="Y":
            self.rebuildrootkey()
        if rebuild_value=="Y":
            self.updaterootvalue()
        if rebuild_trailer=="Y":
            self.updatetrailer()

        rootcatalogID=self.ordered_fdf_key[1]    #obtain ID of root catalog object
                
        with open(outputfdfpath, 'w', encoding='windows-1252') as file:
            #header
            file.write(self.fdf_dict["header"]+"\n")
            #root
            file.write(rootcatalogID+"\n")
            file.write(self.fdf_dict[rootcatalogID]+"\n")
            #annotation objects
            for item in self.ordered_fdf_key[2:-1]:
                file.write(item+"\n")
                file.write(self.fdf_dict[item]+"\n")
            #trailer object
            file.write(self.fdf_dict["trailer"])

    def removeannotation(self, objectid: str) -> None:
        """
        Method that removes provided annotation object from ordered_fdf_key, fdf_dict, root_key and bs_subobject_dict, popup_subobject_dict and parent_subobject_dict
        if the annotation was referenced in the root catalog object - this reference is removed from root_key
        if the annotation to be removed points to a subannotation within a subobject_dict this referenced sub annotation will also be explicitly removed (recursive deletion)

        Input: objectid (str): String value containing the object identifier for the annotation.
        Return: None
        """
        objectid_R=""
        objectid_obj=""
        objecttag=r"^(\d+ \d+ )(R|obj)$"
        objecttagmatch=re.search(objecttag, objectid)
        if objecttagmatch:            
            objectid_R=objecttagmatch.group(1)+"R"
            objectid_obj=objecttagmatch.group(1)+"obj"      

        self.root_key=[item for item in self.root_key if item not in [objectid_obj, objectid_R, objectid]]
        self.ordered_fdf_key=[item for item in self.ordered_fdf_key if item not in [objectid_obj, objectid_R, objectid]]
        #remove occurrence from fdf_dict
        if objectid_obj in self.fdf_dict:
            del self.fdf_dict[objectid_obj]
        elif objectid_R in self.fdf_dict:
            del self.fdf_dict[objectid_R]
        elif objectid in self.fdf_dict:
            del self.fdf_dict[objectid]

        #remove occurrence from subobject_dicts [BS, Parent and Popup subobject dicts] if occurring
        toremove=""
        if objectid_obj in self.bs_subobject_dict:
            toremove=self.bs_subobject_dict.pop(objectid_obj)
        elif objectid_R in self.bs_subobject_dict:
            toremove=self.bs_subobject_dict.pop(objectid_R)
        elif objectid in self.bs_subobject_dict:
            toremove=self.bs_subobject_dict.pop(objectid)

        elif objectid_obj in self.popup_subobject_dict:
            toremove=self.popup_subobject_dict.pop(objectid_obj)
        elif objectid_R in self.popup_subobject_dict:
            toremove=self.popup_subobject_dict.pop(objectid_R)
        elif objectid in self.popup_subobject_dict:
            toremove=self.popup_subobject_dict.pop(objectid)

        elif objectid_obj in self.parent_subobject_dict:
            toremove=self.parent_subobject_dict.pop(objectid_obj)
        elif objectid_R in self.parent_subobject_dict:
            toremove=self.parent_subobject_dict.pop(objectid_R)
        elif objectid in self.parent_subobject_dict:
            toremove=self.parent_subobject_dict.pop(objectid)        

        if toremove !="":
            print(f"Subobject removal triggered for provided object (ID={objectid}): {toremove}.")
            self.removeannotation(toremove)

    
    def qualifyasheaderMSGV1(self, objectid: str) -> bool:
        """
        Method that checks if the value of the contents attribute qualifies as a domain header according to SDTM-MSG V1.
        The method returns True if the value matches the XX=Label syntax where XX must be domain code in upper case and Label contains both up cased and low cased letters, with optional spaces, hyphens and underscores allowed.

        Input: objectid (str): String value containing the object identifier for the annotation.
        Output: bool: True is returned if the text contained in the content attribute matches the expected header annotation pattern XX=Label.
                      False is returned if the text doesn't match the expected pattern, or if the provided objectid does not exist in fdf_key or has no contents attribute available.

        """
        proceed=False
        objecttag2=r"^(\d+ \d+ )R$"    #needed to reroute "\d+ \d+ R" objects towards "\d+ \d+ obj" values present in ordered_fdf_key       
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:             #reroute spelling of object referenced
            objectid=objecttag2match.group(1)+"obj"
        if objectid in self.fdf_dict:
            proceed=True
        if proceed==True:
            proceed=self.hascontent(objectid)
        if proceed==True:        
            textcontent=self.getcontent(objectid)
            headerV1tag=r"^([A-Z]{2,4}|RELREC)\s*\=[a-zA-Z_\-\s]+$"
            headerV1tagmatch=re.search(headerV1tag, textcontent)
            return True if headerV1tagmatch else False
        else:
            print(f"The provided object (ID= {objectid}) was not part of the fdf_dict list or didn't have a contents attribute.")
            return False

    def qualifyasheaderMSGV2(self, objectid: str) -> bool:
        """
        Method that checks if the value of the contents attribute qualifies as a domain header according to SDTM-MSG V2.
        The method returns True if the value matches the XX (Label) syntax where XX must be domain code in upper case and Label contains both upcased and low cased letters, with optional spaces, hyphens and underscores allowed.

        Input: objectid (str): String value containing the object identifier for the annotation.
        Output: bool: True is returned if the text contained in the content attribute matches the expected header annotation pattern XX (Label).
                      False is returned if the text doesn't match the expected pattern, or if the provided objectid does not exist in fdf_key or has no contents attribute available.


        """
        proceed=False
        objecttag2=r"^(\d+ \d+ )R$"    #needed to reroute "\d+ \d+ R" objects towards "\d+ \d+ obj" values present in ordered_fdf_key       
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:             #reroute spelling of object referenced
            objectid=objecttag2match.group(1)+"obj"
        if objectid in self.fdf_dict:
            proceed=True
        if proceed==True:
            proceed=self.hascontent(objectid)
        if proceed==True:        
            textcontent=self.getcontent(objectid)
            headerV2tag=r"^[A-Z]{2,4}\s*\\\([a-zA-Z_\s\-]+\\\)\s*$"
            headerV2tagmatch=re.search(headerV2tag, textcontent)
            return True if headerV2tagmatch else False
        else:
            print(f"The provided object (ID= {objectid}) was not part of the fdf_dict list or didn't have a contents attribute.")
            return False
        
    def hascontent(self, objectid: str) -> bool:
        """
        Method that returns True if the provided objectid has a /Contents attribute.
        It returns False if the provided objectid doesn't contain such /Contents attribute.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Output: bool: True is returned if the /Contents attribute exists.
                      False is returned if the /Contents attribute does not exist, or the provided objectid is not included in the fdf_dict.
        """
        
        objecttag2=r"^(\d+ \d+ )R$"    #needed to reroute "\d+ \d+ R" objects towards "\d+ \d+ obj" values present in fdf_dict       
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:             #reroute spelling of object referenced
            objectid=objecttag2match.group(1)+"obj"
        if objectid in self.fdf_dict:
            annotstring=self.fdf_dict[objectid]
            contenttag=r"(?<!\\)/Contents\("
            contenttagmatch=re.search(contenttag, annotstring)
            return True if contenttagmatch else False
        else:
            print(f"The provided object (ID= {objectid}) was not part of the fdf_dict.")
            return False
         
    def hasc(self, objectid: str) -> bool:
        """
        Method that returns True if the provided objectid has a /C attribute.
        It returns False if the provided objectid doesn't contain such /C attribute.
        
        Input: objectid (str): String value containing the object identifier for the annotation.
        Output: bool: True is returned if the /C attribute exists.
                      False is returned if the /C attribute does not exist, or the provided objectid is not included in the fdf_dict.
        """
        
        objecttag2=r"^(\d+ \d+ )R$"    #needed to reroute "\d+ \d+ R" objects towards "\d+ \d+ obj" values present in fdf_dict       
        objecttag2match=re.search(objecttag2, objectid)
        if objecttag2match:             #reroute spelling of object referenced
            objectid=objecttag2match.group(1)+"obj"
        if objectid in self.fdf_dict:
            annotstring=self.fdf_dict[objectid]
            contenttag=r"(?<!\\)/C\["
            contenttagmatch=re.search(contenttag, annotstring)
            return True if contenttagmatch else False
        else:
            print(f"The provided object (ID= {objectid}) was not part of the fdf_dict.")
            return False 
            
    @staticmethod
    def removercreturns(fdfrcxml: str) -> str:
        """
        Method that removed a backslash followed by a new line or carriage return.
        This method needs to be called on the xml or html string embedded in the fdf annotations that occurs after 255 xml or html characters respectively.
        Not removing this will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html)
        Output: string (containing xml or html), but without the backslash + newline/carriage return character sequences inside it
        """
        
        if fdfrcxml=="":
            return ""
        return re.sub(r'\\[\r\n]', '', fdfrcxml)
    

    @staticmethod
    def addrcreturns(fdfxml: str) -> str:
        """
        Method that adds a backslash followed by a new line character in the provided fdfxml string.
        This method ensures that all updated strings are again split into chunks of max 255 characters as observed in fdf extracts.
        Not inserting this will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html)
        Output: string (containing xml or html), with the backslash +newline character added after each chunk of 255 chars
        """
        toprocess: str=fdfxml
        result: str=""
        inbetweenlist=[]
        while toprocess != "":                            
            if len(toprocess)<=255:
                inbetweenlist.append(toprocess)
                toprocess=""
            else:
                inbetweenlist.append(toprocess[0:255]) 
                toprocess=toprocess[255:]
        result="\\\n".join(inbetweenlist)
        return result


    @staticmethod
    def string_to_dict(inputstring: str, keyvalueseparator: str, pairseparator: str) -> dict:
        """
        Method that extracts all key-value pairs from an input string and returns them as a dictionary
        
        This method assumes the string only consists of key-value pairs which are separated by the provided pairseparator argument.
        Within each pair it is assumed that the key and value are separated by the provided keyvalueseparator argument.
        Note that the obtained keys and values will be stripped before added into the dictionary.
        
        Input:
        inputstring: str: string containing one or more key-value pairs
        keyvalueseparator: str: character or set of characters present in the inputstring that separates each key from its associated value. Usually this is a colon ':'
        pairseparator: str: character or set of characters present in the inputstring that separates between multiple key-value pairs. Usually this is a semicolon ';'
        
        Output: Dictionary (dict) containing all keys and associated values identified in the inputstring
        
        """
        pairs = inputstring.split(pairseparator)     #obtain list of all key-value pairs in inputstring
        style_dict = dict()
        for pair in pairs:
            if keyvalueseparator in pair:            
                key, value = pair.split(keyvalueseparator)      #split each identified pair in its associated dictionary key and value
                style_dict[key.strip()] = value.strip()
            else:
                print(f"Provided inputstring does not contain expected keyvalueseparator within a pair. inputstring={inputstring}, pair={pair}, keyvalueseparator={keyvalueseparator}")
        return style_dict
    
    
    @staticmethod
    def dict_to_string(inputdict: dict, keyvalueseparator: str, pairseparator: str) -> str:
        """
        Method that converts the provided inputdict dictionary into a single string, separating the key-value pairs by using the provided keyvalueseparator, 
        and separating the different entries in the inputdict by using the provided pairseparator.
        
        Input:
        inputdictstring: dict: dictionary containing one or more entries
        keyvalueseparator: str: character or set of characters present in the inputstring that separates each key from its associated value. Usually this is a colon ':'.
        pairseparator: str: character or set of characters present in the inputstring that separates between multiple key-value pairs. Usually this is a semicolon ';'.
        
        Output: String (str) containing all the dictionary entries provided in the inputdict concatenated into a single output string
        
        """
        dictstring=""
        if inputdict=={}:
            return dictstring
        for key, value in inputdict.items():           
            if dictstring.strip() != "":
                dictstring=dictstring+pairseparator
            dictstring=dictstring+key+keyvalueseparator+value
        
        return dictstring
    
    
    @staticmethod
    def string_to_dict_separator(inputstring: str, keyvalueseparator: str, pairseparator: str) -> dict:
        """
        Method that lists whether each key:value pair provided within the inputstring uses spaces after the keyvalueseparator for the given key which would be omitted from any dictionary assignment.
        This method allows to minimize unwanted changes when manipulating the attributes provided in the inputstring
        
        This method assumes the string only consists of key-value pairs which are separated by the provided pairseparator argument.
        Within each pair it is assumed that the key and value are separated by the provided keyvalueseparator argument.
        Note that the obtained keys and values will be before added into the dictionary.
        
        Input:
        inputstring: str: string containing one or more key-value pairs
        keyvalueseparator: str: character or set of characters present in the inputstring that separates each key from its associated value. Usually this is a colon ':'
        pairseparator: str: character or set of characters present in the inputstring that separates between multiple key-value pairs. Usually this is a semicolon ';'
        
        Output: Dictionary (dict) containing all keys and with the associated decode of  'space' or 'nospace' if the keyvalueseparator is followed by a space or no space respectively within the provided inputstring.
        """
        pairs = inputstring.split(pairseparator)     #obtain list of all key-value pairs in inputstring
        space_dict = dict()
        for pair in pairs:
            if keyvalueseparator in pair:            
                key, value = pair.split(keyvalueseparator)      #split each identified pair in its associated dictionary key and value
                if value[0]==" ":
                    space_dict[key.strip()] = "space"
                else:
                    space_dict[key.strip()] = "nospace"
            else:
                print(f"Provided inputstring does not contain expected keyvalueseparator within a pair. inputstring={inputstring}, pair={pair}, keyvalueseparator={keyvalueseparator}")
        return space_dict
        
    @staticmethod
    def getrcstyles(fdfrcxml: str) -> list:
        """
        Method that extracts the values of all occurrences of the styles attribute included in the provided xml or html string."
        
        This method assumes the embedded line splits in the xml have already been actively removed from the input fdfrcxml string by applying the removercreturns after having obtained it via getrccontent, prior to feeding it into this method.
        Skipping this step will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html) that has already been processed by the removercreturns method
        Output: List of lists containing all encountered style attributes together with the surrounding xml/html content.
            Outer list: 
                The first element within the outer list contains the main style attribute value encountered.
                Any other element within the outer list contains additional style attribute values encountered after the definition of the main style attribute, across the different spans included within the xml/html string provided.
            The inner list contains 2 elements for each element: 
                The first element contains the xml/html text preceding the style attribute of interest. 
                    If no style attribute is encountered this first element will contain the full html/xml string provided.
                    Otherwise it'll contain the xml/html content provided between previous style attribute value listed on previous outer list element and the current one listed in this element of the outer list.
                The second element contains the value of the style attribute as occurring inside the xml or html string provided.
                    In case no style attribute is remaining inside the input xml/html to be processed, then the value of the second element will be an empty string.                
            In case the provided input fdfrcxml string provided is empty the method will return a list containing an empty inner list [[]]
        """

        if fdfrcxml=="":
            return [[]]
        styletag=r"(\bstyle\s*=\s*\")([^\"]*?)\""
        toprocess=fdfrcxml  #string to decompose until fully processed (i.e. empty)
        outputlist=[]
        while toprocess !="":
            styletagmatch=re.search(styletag, toprocess)
            if styletagmatch:
                stylevalue=toprocess[styletagmatch.start(2):styletagmatch.end(2)]
                outputlist.append([toprocess[0:styletagmatch.start(2)], stylevalue, fdf_annotations.string_to_dict(stylevalue, ':',';')])
                toprocess=toprocess[styletagmatch.end(2):]                
            else:
                outputlist.append([toprocess, "", dict()])
                toprocess=""        
        return outputlist
    
    @staticmethod
    def rcstyles_setmasterstyle(rcstyleslist: list, rcstylesdict: dict) -> list:
        """
        Method that takes the rcstyles list as input (obtained from method getrcstyles) and sets the style attribute dictionary of the first row (i.e. last element in first row) to  the dictionary provided rcstylesdict. 
        It also converts the dictionary to a string to populate the second element of the first row accordingly.
        This method is useful to set the standard font-size, text-align, color, font-weight, font-style, font-family, font-stretch within the rc prior to retranslating the rcstyleslist to the rcstring using method rcstyles_to_rccontentstring.
        Note: it is recommended to not define bold font-weight in the master style, as this can be defined into a span afterwards. This allows to define a single master style for all text annotation objects.
        Note: method dict_to_string is called from within this method.

        Input: 
            rcstyleslist (list): list obtained from method getrcstyles
            rcstylesdict (dict): dictionary defining the default rc style for the /RC object (prior to applying any spans). 
                It should define font-size, text-align, color, font-weight, font-style, font-family, font-stretch.
        Output: a list that is identical to the rcstyleslist provided,  except for the third and second element from first row being updated to the provided dictionary in input and its associated string representation respectively.                
            In case the provided input fdfrcxml string provided is empty, or the dictionary on the first row is empty (i.e. no style tag existing) then this method will return the inputlist as such
        """

        if rcstyleslist==[]:
            return rcstyleslist
        if rcstyleslist[0][2]=={}:
            return rcstyleslist
        rcstyleslist[0][2]={key:value for key, value in rcstylesdict.items()}
        rcstyleslist[0][1]=fdf_annotations.dict_to_string(rcstylesdict, ':', ';')
        return rcstyleslist
    
    @staticmethod
    def rc_dropspans(fdfrcxml: str) -> str:
        """
        Method that removes the span xml tags in the provided rc xml string.
        Note that only the tags are removed. Any content between the opening span tag and closing span tag is preserved. 
        This operation is usually required to ensure a single style policy to be applied on the entire annotation without touching the text to display.
        
        This method assumes the embedded line splits in the xml have already been actively removed from the input fdfrcxml string by the removercreturns prior to feeding it into this method.
        Skipping this step will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml) that has already been processed by the removercreturns method
        Output: string no longer containing <span...> or </span> tags. 
        """

        toprocess="Y"
        processed=fdfrcxml
        spanopentag=r"(\<\s*?span\s+?.*?\>)"
        spanclosetag=r"(\<\s*?/span\>)"
        while toprocess=="Y":
            toprocess="N"
            spanopentagmatch=re.search(spanopentag, processed)
            if spanopentagmatch:
                processed=processed[0:spanopentagmatch.start(1)] + processed[spanopentagmatch.end(1):]
                toprocess="Y"
            spanclosetagmatch=re.search(spanclosetag, processed)
            if spanclosetagmatch:
                processed=processed[0:spanclosetagmatch.start(1)] + processed[spanclosetagmatch.end(1):]
                toprocess="Y"
        return processed
    
    @staticmethod
    def rc_insertspan(fdfrcxml: str, openingspantag:str, closingspantag: str) -> str:
        """
        Method that inserts an opening span tag immediately after the <p...> tag and a closing span tag immediately before the </p> tag within the provided fdfrcxml string.
        This method assumes there's only one <p...> element included within the provided fdfrcxml string.
        Note that only the tags are added. All content present in the input fdfrcxml string in between the opening and closing location will therefore become the value of the inserted span tag. 
        This operation is usually required to insert a bold font-weight policy on top of the standard master style within the fdfrcxml,  i.e., after method getrccontent, removercreturns, rc_dropspans, getrcstyles, rcstyles_setmasterstyles have been invoked.

        This method assumes the embedded line splits in the xml have already been actively removed from the input fdfrcxml string by the removercreturns prior to feeding it into this method.
        Skipping this step will interfere with the analysis of the FDF content.

        Input: 
            fdfrcxml (str): String (containing xml) that has already been processed by the removercreturns method.
            openingspantag (str): String that contains the opening span tag that is to be inserted. E.g., "<span style="font-weight:bold">".
            closingspantag (str): String that contains the closing span tag that is to be inserted. E.g., "</span>". 
        Output: string (str) with the provided opening and closing span tag embedded into it.
            In case the provided fdfrcxmlstring does not contain both  <p...> and </p> tags the provided input fdfrcxml string is returned.
            In case the closing tag would appear prior to the opening tag the provided input fdfrcxml string is returned.
        """
        
        popentag=r"(\<\s*p\s+?.*?\>)"
        pclosetag=r"(\</p\>)"
        popentagmatch=re.search(popentag, fdfrcxml)
        pclosetagmatch=re.search(pclosetag, fdfrcxml)
        if popentagmatch and pclosetagmatch:
            if popentagmatch.end(1) < pclosetagmatch.end(1):
                prestring=fdfrcxml[:popentagmatch.end(1)]+openingspantag
                midstring=fdfrcxml[popentagmatch.end(1):pclosetagmatch.start(1)]+closingspantag
                endstring=fdfrcxml[pclosetagmatch.start(1):]
                return prestring+midstring+endstring
            
            else:
                print(f'Input fdfrcxml string is compromised: The </p> closing tag appears prior to the <p ...> opening tag: {fdfrcxml}')
                return fdfrcxml
        else:
            print(f'No <p ...> opening and </p> closing tag found in provided input fdfrcxml string: {fdfrcxml}')
            return fdfrcxml

    @staticmethod
    def rcstyles_to_rccontentstring(rcstyleslist: list) -> str:
        """
        Method that takes an updated rcstyles list as input and translates it back to a rcstyles string that can be fed into updaterccontent afterwards
        Input: 
            rcstyleslist (list): list obtained from method getrcstyles, that has undergone modifications to update the rcstyles via e.g., rc_dropspans, rcstyles_setmasterstyle
            
        Output: (str): a /RC string that can be used as input in method updaterccontent to update the /RC attribute of the annotation accordingly
        """

        return_rc_string=""
        if rcstyleslist==[]:
            return return_rc_string
        for row in rcstyleslist:
            updatedrowstylestring=""
            if row[1] !='':
                updatedrowstylestring=fdf_annotations.dict_to_string(row[2], ':',';')
            return_rc_string=return_rc_string+row[0]+updatedrowstylestring
                   
        return return_rc_string
    

    @staticmethod
    def getdsattributes(fdfdsstr: str) -> list:
        """
        Method that translates the provided DS contents string (fdfdsstr) into a list containing a dictionary.
                
        Input: fdfdsstr: string contaning the /DS contents obtained using getdscontent method
        Output: List containing 3 elements
             
                The first element within the list contains the provided fdfdsstr.
                The second element contains a dictionary for each encountered key-value pair within the provided fdfdsstr value. A colon is assumed to separate key-value pairs.
                The third element contains the key-value separator for each associated key. This allows to compensate for FDF behavior where certain attributes might (not) get preceded with a space
                
            
        """

        if fdfdsstr=="":
            return ["", {}, {}]
                
        return [fdfdsstr, fdf_annotations.string_to_dict(fdfdsstr, ':',';'), fdf_annotations.string_to_dict_separator(fdfdsstr, ':',';')]
    

    @staticmethod
    def rgb_inttohex(rgbintcolorstring: str) -> str:
        """
        Method that translates the provided rgbintcolorstring integer values (0-255) to a hexadecimal color string value.
                
        Input: rgbintcolorstr: string containing the 3 int values (0-255), for red, green, blue respectively, separated by a space. The string may be encapsulated with square brackets.
        Output: string containing a hexadecimal rgb representation, consisting of a hashtag followed by the rgb components represented in hexadecimal characters accordingly (no spacing, 2 hex chars per component for r, g, b)
             E.g. "0 0 255" or "[0 0 255]" --> "#0000FF"  
             In case the provided rgbintcolorstring does not meet the expected formatting or is empty, an empty string will be returned.
        """

        if rgbintcolorstring=="":
            return ""
        intrgbtag=r"^\[?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*\]?$"      #optional square brackets followed by optional space(s), each rgb component can max consist of 3 digits, separated by at least 1 space.
        intrgbstrmatch=re.search(intrgbtag, rgbintcolorstring)
        if intrgbstrmatch:
            return "#" + format(int(intrgbstrmatch.group(1)), "02X") + format(int(intrgbstrmatch.group(2)), "02X") + format(int(intrgbstrmatch.group(3)), "02X")      #zero-padding to 2 digits for each rgb component
        return ""    #input does not match expected structure 

    @staticmethod
    def rgb_hextoint(rgbhexcolorstring: str) -> str:
        """
        Method that translates the provided rgbhexcolorstring to a string containing the 3 rgb values expressed as integer values (0-255) separated by a space.
                
        Input: rgbhexcolorstring: string consisting of a hashtag followed by the rgb components represented in hexadecimal characters accordingly (no spacing, 2 hex chars per component for r, g, b; E.g., '#AA09F1')
        Output: string containing the rgb components expressed as integer values (0-255) for the r, g, b components respectively, separated by a space.
             E.g. "#0000FF" --> "0 0 255"  
             In case the provided rgbhexcolorstring does not meet the expected formatting or is empty, an empty string will be returned.
        """

        if rgbhexcolorstring=="":
            return ""
        hexrgbtag=r"^#([0-9A-F]{2})([0-9A-F]{2})([0-9A-F]{2})$"      # hashtag followed by 6 hexadecimal chars
        hexrgbstrmatch=re.search(hexrgbtag, rgbhexcolorstring)
        if hexrgbstrmatch:
            return str(int(hexrgbstrmatch.group(1), 16)) + " " + str(int(hexrgbstrmatch.group(2), 16)) + " " + str(int(hexrgbstrmatch.group(3), 16))
        return ""    #input does not match expected structure     

    @staticmethod
    def rgb_fractoint(rgbfraccolorstring: str) -> str:
        """
        Method that translates the provided rgbfraccolorstring to a string containing the 3 rgb values expressed as integer values (0-255) separated by a space.
                
        Input: rgbfraccolorstring: string consisting of a fraction of 1 representation of the rgb values respectively, separated by a space, encapsulated between square brackets. (E.g., "[1.0 0.1234 0.0]" or "[1 0.1234 0]")
        Output: string containing the rgb components expressed as integer values (0-255) for the r, g, b components respectively, separated by a space.
             E.g. "[1.0 0.123456 0.0]" --> "255 31 0"  
             In case the provided rgbfraccolorstring does not meet the expected formatting or is empty, an empty string will be returned.
        """

        if rgbfraccolorstring=="":
            return ""
        fracrgbtag=r"^\[([01](\.\d{1,6}){0,1})\s+([01](\.\d{1,6}){0,1})\s+([01](\.\d{1,6}){0,1})\]$"      # 0 or 1 followed by decimal separator (.) and followed by at least one and up to 6 decimals for each component
        fracrgbstrmatch=re.search(fracrgbtag, rgbfraccolorstring)
        if fracrgbstrmatch:
            return str(int(round(float(fracrgbstrmatch.group(1))*255))) + " " + str(int(round(float(fracrgbstrmatch.group(3))*255))) + " " + str(int(round(float(fracrgbstrmatch.group(5))*255)))
        return ""    #input does not match expected structure
    
    
    @staticmethod
    def rgb_c_inttofrac(rgbintcolorstring: str) -> str:
        """
        Method that translates the provided rgbintcolorstring integer values (0-255) to a fractional (0.0-1.0) color string value.
        the returned value can be embedded in the /C tag as its precision varies from minimally 1 to up to 6 decimals. Do not use this function to populate the /DA tag for the rg value as the latter uses different ranges of precision.
                
        Input: rgbintcolorstr: string containing the 3 int values (0-255), for red, green, blue respectively, separated by a space. The string may be encapsulated with square brackets.
        Output: string containing a fractional rgb representation, consisting of float values for the r, g, b components respectively separated by a space, encapsulated in square brackets. Precision ranges between 1 decimal to up to 6 decimals.
            E.g., "255 31 0" or "[255 31 0]" --> "[1.0 0.121569 0.0]"  
            In case the provided rgbintcolorstring does not meet the expected formatting or is empty, an empty string will be returned.
        """

        if rgbintcolorstring=="":
            return ""
        intrgbtag=r"^\[?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*\]?$"      #optional square brackets followed by optional space(s), each rgb component can max consist of 3 digits, separated by at least 1 space.
        intrgbstrmatch=re.search(intrgbtag, rgbintcolorstring)
        if intrgbstrmatch:
            r=("{:f}".format(int(intrgbstrmatch.group(1))/255)).rstrip("0") 
            g=("{:f}".format(int(intrgbstrmatch.group(2))/255)).rstrip("0") 
            b=("{:f}".format(int(intrgbstrmatch.group(3))/255)).rstrip("0")
            if r[-1]==".":
                r=r+"0"
            if g[-1]==".":
                g=g+"0"
            if b[-1]==".":
                b=b+"0"
            return "[" +r + " " + g + " " + b +  "]"
        return ""    #input does not match expected structure 
    
    @staticmethod
    def rgb_da_inttofrac(rgbintcolorstring: str) -> str:
        """
        Method that translates the provided rgbintcolorstring integer values (0-255) to a fractional (0-1) color string value.
        the returned value can be embedded in the /DA tag as its precision varies from minimally 0 to up to 4 decimals. Do not use this function to populate the /C tag as the latter uses different ranges of precision.
                
        Input: rgbintcolorstr: string containing the 3 int values (0-255), for red, green, blue respectively, separated by a space. The string may be encapsulated with square brackets.
        Output: string containing a fractional rgb representation, consisting of float values for the r, g, b components respectively separated by a space. Precision ranges between 0 to up to 4 decimals. 
            Note it does not encapsulate the result in square brackets.
            E.g., "255 31 0" or "[255 31 0]" --> "1 0.1216 0]"  
            In case the provided rgbintcolorstring does not meet the expected formatting or is empty, an empty string will be returned.
        """

        if rgbintcolorstring=="":
            return ""
        intrgbtag=r"^\[?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*\]?$"      #optional square brackets followed by optional space(s), each rgb component can max consist of 3 digits, separated by at least 1 space.
        intrgbstrmatch=re.search(intrgbtag, rgbintcolorstring)
        if intrgbstrmatch:
            r=("{:.4f}".format(int(intrgbstrmatch.group(1))/255)).rstrip("0").rstrip(".") 
            g=("{:.4f}".format(int(intrgbstrmatch.group(2))/255)).rstrip("0").rstrip(".") 
            b=("{:.4f}".format(int(intrgbstrmatch.group(3))/255)).rstrip("0").rstrip(".")            
            return r + " " + g + " " + b
        return ""    #input does not match expected structure 

    @staticmethod
    def rc_html_to_xml (rchtmlstring: str, bodystring: str) -> str:
        """
        Method that replaces html /RC contents to associated xml /RC contents to allow for harmonization:
        It replaces the <html:body ...>  opening tag to a provided <body ...> element.
        It removes html: from opening <html:...> and closing </html:...> tags.
        It adds the xml header at the beginning of the string (only if <html:body ...> tag is discovered).

        Note: Method removercreturns should have been executed on the input rchtmlstring prior to calling this method to avoid interference of the newlines/carriage appearing in the /RC values. 
        Note: This method calls method rc_hashtml to verify whether the provided string contains html tags or not. 

        Input:
            rchtmlstring (str): String obtained using getrcontent, that contains html iso xml.
            bodystring (str): String containing the xml equivalent of the html opening body tag that is to be replaced.
        Output:
            String containing the html tags replaced by xml.
            In case no html tags are detected, the provided rchtmlstring is returned as such.

        """
        toreturn=rchtmlstring
        if fdf_annotations.rc_hashtml(toreturn)==False:
            return toreturn
        #replace htmlbody opening tag by harcdoded xml body tag
        htmlbodytag=r"<html:body .*?>"
        htmlbodytagmatch=re.search(htmlbodytag, toreturn)
        if htmlbodytagmatch:            
            #replace body tag with xml body tag
            toreturn=toreturn[0:htmlbodytagmatch.start()]+bodystring+toreturn[htmlbodytagmatch.end():]
            #insert xml header
            toreturn='<?xml version="1.0"?>'+toreturn
        else:
            print("No html body tag replaced in provided rchtmlstring.")
        #remove html: from <html: ...> tags
        htmltag=r"<html:"
        toprocess=True
        while toprocess:
            htmltagmatch=re.search(htmltag, toreturn)
            if htmltagmatch:
                toreturn=toreturn[0:htmltagmatch.start()]+"<"+toreturn[htmltagmatch.end():]
            else:
                toprocess=False
        #remove html: from </html: ...> tags
        htmlclosetag=r"<\/html:"
        toprocess=True
        while toprocess:
            htmlclosetagmatch=re.search(htmlclosetag, toreturn)
            if htmlclosetagmatch:
                toreturn=toreturn[0:htmlclosetagmatch.start()]+"</"+toreturn[htmlclosetagmatch.end():]
            else:
                toprocess=False
        return toreturn

    @staticmethod
    def rc_hashtml(rchtmlstring: str) -> bool:
        """
        Method that returns True if the provided rchtmlstring does contain html tags. 
        The rchtmlstring is assumed to be obtained using method getrccontent, and should be processed using method removercreturns prior to feeding it into this method to avoid interference.

        Input:
            rchtmlstring (str): String obtained using getrcontent, that contains html iso xml.
        Output:
            bool: 
            True is returned if the provided rchtmlstring contains <html:...> or </html:> tags.
            False is returned otherwise.
        """

        htmltag=r"</?html:"
        htmltagmatch=re.search(htmltag, rchtmlstring)
        if htmltagmatch:            
            return True
        return False
         




#additional methods to be added here