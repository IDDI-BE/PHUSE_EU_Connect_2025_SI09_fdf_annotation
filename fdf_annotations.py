import re
import io

class fdf_annotations:
    root_key=[]                #list containing all objects referenced from the root catalog object
    ordered_fdf_key=[]
    fdf_dict={}
    bs_subobject_dict={}       #border style subobject references - referenced objects not included in root_key
    popup_subobject_dict={}    #popup style subobject references - referenced objects included in root_key
    parent_subobject_dict={}   #parent style subobject references - referenced objects included in root_key
    interobjectcounter=0
    
    def __init__(self, inputfdfpath: str) -> None:
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
        #iterate over elements present in ordered_fdf_key:, i.e. the object IDs of each annotation
        return iter(self.ordered_fdf_key)
    
    
    def getannotation(self, objectid) -> str:
        """
        Method that returns the annotation value for the provided annotation id. Note that annotation value refers to the full object.
        If the provided object id value is not existing in the fdf_dict it will return None.

        Input: object id
        Return: string value containing the value of the annotation stored in the fdf_dict for the provided objectid key
        """

        if objectid in self.fdf_dict:     #do not add () after the dict or it will crash            
            return self.fdf_dict[objectid]
        else: 
            return None

    def getrccontent(self, objectid) -> list:
        """
        Method that returns the annotation value for the provided annotation id split into a list of max 3 elements to allow for easily accessing and/or updating the xml/html part embedded in the /RC tag of the FDF object using other methods.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: object id
        Return: list containing the value of the /RC tag as second element. 
            The first element of the returned list contains the content of the provided objectid prior to the /RC tag content.
            The third element of the returned list contains the content of the provided objectid after the /RC tag content.
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            rclist=[]
            annotstring=self.fdf_dict[objectid]
            rcstarttag=r"(?<!\\)/RC\("
            rcstartmatch=re.search(rcstarttag, annotstring)
            if rcstartmatch:                
                rclist.append(annotstring[0:rcstartmatch.end()])
                toprocess=annotstring[rcstartmatch.end():]
                rcendtag=r"(?<!\\)\)"
                rcendmatch=re.search(rcendtag, toprocess)
                if rcendmatch:
                    rclist.append(toprocess[0:rcendmatch.start()])
                    rclist.append(toprocess[rcendmatch.start():])
                else:
                    print(f"No /RC closing parenthesis found for provided object {objectid}.")
                    rclist.append(toprocess)
                return rclist
            else:
                print(f"No /RC opening tag found in provided object {objectid}.")
                return [self.fdf_dict[objectid]]        #no RC tag found

    def getdscontent(self, objectid) -> list:
        """
        Method that returns the annotation value for the provided annotation id split into a list of max 3 elements to allow for easily accessing and updating the /DS tag of the FDF object using other methods.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: object id
        Return: list containing the value of the /DS tag as second element. 
            The first element of the returned list contains the content of the provided objectid prior to the /DS tag content.
            The third element of the returned list contains the content of the provided objectid after the /DS tag content.
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            dslist=[]
            annotstring=self.fdf_dict[objectid]
            dsstarttag=r"(?<!\\)/DS\("
            dsstartmatch=re.search(dsstarttag, annotstring)
            if dsstartmatch:                
                dslist.append(annotstring[0:dsstartmatch.end()])
                toprocess=annotstring[dsstartmatch.end():]
                dsendtag=r"(?<!\\)\)"
                dsendmatch=re.search(dsendtag, toprocess)
                if dsendmatch:
                    dslist.append(toprocess[0:dsendmatch.start()])
                    dslist.append(toprocess[dsendmatch.start():])
                else:
                    print(f"No /DS closing parenthesis found for provided object {objectid}.")
                    dslist.append(toprocess)
                return dslist
            else:
                print(f"No /DS opening tag found in provided object {objectid}.")
                return [self.fdf_dict[objectid]]        #no DS tag found
    
    def getdacontent(self, objectid) -> list:
        """
        Method that returns the annotation value for the provided annotation id split into a list of max 3 elements to allow for easily accessing and updating /DA tag of the FDF object using other methods.
        If the provided object id value is not existing in the fdf_dict it will return None.
        
        Input: object id
        Return: list containing the value of the /DA tag as second element. 
            The first element of the returned list contains the content of the provided objectid prior to the /DA tag content.
            The third element of the returned list contains the content of the provided objectid after the /DA tag content.
        """

        if objectid not in self.fdf_dict:
            return None
        if objectid in self.fdf_dict:
            dalist=[]
            annotstring=self.fdf_dict[objectid]
            dastarttag=r"(?<!\\)/DA\("
            dastartmatch=re.search(dastarttag, annotstring)
            if dastartmatch:                
                dalist.append(annotstring[0:dastartmatch.end()])
                toprocess=annotstring[dastartmatch.end():]
                daendtag=r"(?<!\\)\)"
                daendmatch=re.search(daendtag, toprocess)
                if daendmatch:
                    dalist.append(toprocess[0:daendmatch.start()])
                    dalist.append(toprocess[daendmatch.start():])
                else:
                    print(f"No /DA closing parenthesis found for provided object {objectid}.")
                    dalist.append(toprocess)
                return dalist
            else:
                print(f"No /DA opening tag found in provided object {objectid}.")
                return [self.fdf_dict[objectid]]        #no DA tag found

    

    def updaterccontent(self, objectid, updatedrcstring) -> None:
        """
        Method that updates the /RC value contained within the annotation ID.
        No update is performed if no /RC tag is contained within the annotation - note that the RC tag must have a proper opening and closing parenthesis to be qualified as present.
        Note: This method calls the addrcreturns method to split the provided updatedrcstring in chunks of 255 chars ending with a backslash followed by a new line
        
        Input: 
            objectid=object id
            updatedrcstring= updated string that will replace the /RC contents within the annotation object
        
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
               
    def updatedscontent(self, objectid, updateddsstring) -> None:
        """
        Method that updates the /DS value contained within the annotation ID.
        No update is performed if no /DS tag is contained within the annotation - note that the DS tag must have a proper opening and closing parenthesis to be qualified as present.
          
        Input: 
            objectid=object id
            updateddsstring= updated string that will replace the /DS contents within the annotation object
        
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

    def updatedacontent(self, objectid, updateddastring) -> None:
        """
        Method that updates the /DA value contained within the annotation ID.
        No update is performed if no /DA tag is contained within the annotation - note that the DA tag must have a proper opening and closing parenthesis to be qualified as present.
          
        Input: 
            objectid=object id
            updateddastring= updated string that will replace the /DA contents within the annotation object
        
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

        Input:
            objectid=object id
        Return:
            int containing the page number
            In case the object has no page atribute, or the provided object could not be found it will return None.
        
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
        Method that returns the /Rect value as a string for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /Rect attribute it will return None.
        
        Input: 
            objectid: string: object id
        Return: String containing the Rect value enclosed in square brackets
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        recttag=r"(?<!\\)/Rect(\[.*\])"
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
            objectid: string: object id
            rectstring: string: value that will be assigned to the /Rect tag. Note: the provided value should be encapsulated within square brackets.
        Return: None
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        recttag=r"(?<!\\)/Rect(\[.*\])"         
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
        
        Input: 
            objectid: string: object id
        Return: String containing the /C value enclosed in square brackets
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        ctag=r"(?<!\\)/C(\[.*\])"
        cmatch=re.search(ctag, self.fdf_dict[objectid])
        if cmatch:                        
            return str(cmatch.group(1)) 
        print(f"The provided object (ID= {objectid}) has no /C attribute.") 
        return None

    def setc(self, objectid: str, cstring: str) -> None:
        """
        Method that updates the /C value with the provided cstring value for the provided annotation id.
        If the provided object id value is not existing in the fdf_dict it will return None.
        If the provided object id has no /Rect attribute it will return None.
        
        Input: 
            objectid: string: object id
            cstring: string: value that will be assigned to the /C tag. Note: the provided value should be encapsulated within square brackets.
        Return: None
        """

        if objectid not in self.fdf_dict:
            print(f"The provided object (ID= {objectid}) could not be found within the fdf.")      
            return None       
        ctag=r"(?<!\\)/C(\[.*\])"         
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
        Method that adds a provided objectid to the root catalog object at the provided position within he list.

        The method will only treat provided objectid values of the ofllowing format: "\d+ \d+ R" or "\d+ \d+ obj", E.g., "16 0 R" or "17 0 obj"

        Input Arguments:
            objectid: (str) object identifier to be inserted into the root catalog object list  (root_key)
            insertposition: (int) indexposition where the provided objectid is to be inserted into the root catalog object list (root_key)
                A value of -1 means that the object will be inserted in the last position in the root catalog object list (root_key)
        Return: None
        
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
        Note that this method does not update the rootvalue present in the fdf_dict. The latter is done during rexport of the object to fdf.

        Input argument: None
        Return: None 
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
        Method that updates the trailer element in the fdf_dict and that ensures that trailer is present once as last itme in the ordered_fdf_key list.
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
        Method that exports the object to fdf file.
        The optional arguments allow to rebuild the root_key, root_value and trailer of the fdf_dict object
        
        Inputs:
            outputpath(str): output path of the target fdf file the object should be exported to 
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
        if the annotation to be removed points  to a subannotation within a subobject_dict this referenced sub annotation will also be explicitly removed (recursive deletion)

        Input Argument: objectid
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
            
    @staticmethod
    def removercreturns(fdfrcxml: str) -> str:
        """
        Method that removed a backslash followed by a new line or carriage return.
        This method needs to be called on the xml or html string embedded in the fdf annotations that occurs after 255 xml or html characters respectively.
        Not removing this will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html)
        Output: string (containing xml or html, but without the (backslash +newline/carriage return) character sequences inside it)
        """
        
        if fdfrcxml=="":
            return ""
        return re.sub(r'\\[\r\n]', '', fdfrcxml)
    
    @staticmethod
    def addrcreturns(fdfxml: str) -> str:
        """
        Method that adds a backslash followed by a new line and carriage return in the provided fdfxml string.
        This method ensures that all updated strings are again split into chunks of max 255 characters as observed in fdf extracts.
        Not removing this will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html)
        Output: string (containing xml or html, but without the (backslash +newline/carriage return) character sequences inside it)
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
        Note that the obtained keys and vlaues will be stripped  before added into the dictionary.
        
        Input:
        inputstring: str: string containing one or more key-value pairs
        keyvalueseparator: str: character or set of characters present in the inputstring that separates each key  from its associated value. Typically this is a colon ':'
        pairseparator: str: character or set of characters present in the inputstring that separates between multiple key-value pairs. Typically this is a semicolon ';'
        
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
    def string_to_dict_separator(inputstring: str, keyvalueseparator: str, pairseparator: str) -> dict:
        """
        Method that lists whether each key:value pair provided within the inputstring uses spaces after the keyvalueseparator for the given key which would be omitted from any dictionary assignment.
        This method allows to minimize unwanted changes when manipulating the attributes provided in the inputstring
        
        This method assumes the string only consists of key-value pairs which are separated by the provided pairseparator argument.
        Within each pair it is assumed that the key and value are separated by the provided keyvalueseparator argument.
        Note that the obtained keys and vlaues will be stripped  before added into the dictionary.
        
        Input:
        inputstring: str: string containing one or more key-value pairs
        keyvalueseparator: str: character or set of characters present in the inputstring that separates each key  from its associated value. Typically this is a colon ':'
        pairseparator: str: character or set of characters present in the inputstring that separates between multiple key-value pairs. Typically this is a semicolon ';'
        
        Output: Dictionary (dict) containing all keys and with the associated decode of  'space' or 'nospace' if the keyvalueseparator is followed by a space or no space respectively within the provided inpuststring.
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
        
        This method assumes the embedded line splits in the xml have already been actively removed form the input fdfrcxml string by the removercreturns prior to feeding it into this method.
        Skipping this step will interfere with the analysis of the FDF content.

        Input: fdfrcxml: string (containing xml or html) that has already been processed by the removercreturns method
        Output: List of lists containing all encountered style attributes together with the surrounding xml/html content.
            Outer list: 
                The first element within the outer list contains the main style attribute value encountered.
                Any other element within the outer list contains additional style attribute values encountered after the definition of the main style attribute, across the different spans included within the xml/html string provided.
            The inner list contains 2 elements for each element: 
                The first element contains the xml/html text preceeding the style attribute of interest. 
                    If no style attribute is encountered this first element will contain the full html/xml string provided.
                    Otherwise it'll contain the xml/html content provided between previous style attribute value listed on previous outer list element and the current one listed in this emement of the outer list.
                The second element contains the value of the style attribute as occurring inside the xml or html string provided.
                    In case no style attribute is remaining inside the input xml/html to be processed, then the value of the second element will be an empty string.                
            In case the provided input fdfrcxml string provided is emptyn the method will return a list containing an empty inner list [[]]
        """

        if fdfrcxml=="":
            return [[]]
        styletag=r"(\bstyle\w*=\w*\")([^\"]*?)\""
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
    def getdsattributes(fdfdsstr: str) -> list:
        """
        Method that translates the provided DS contents string (fdfdsstr) into a dictionary.
                
        Input: fdfdsstr: string contaning the /DS contents obtained using getdscontent method
        Output: List containing 3 elements
             
                The first element within the list contains the provided fdfdsstr.
                The second element contains a dictionary for each encountered key-value pair within the provided fdfdsstr value. A colon is assumed to separate key-value pairs.
                The third element contains the key-value separator for each associated key. This allows to compensate for FDF behavior where certain attributes might (not) get preceeded with a space
                
            
        """

        if fdfdsstr=="":
            return ["", {}, {}]
                
        return [fdfdsstr, fdf_annotations.string_to_dict(fdfdsstr, ':',';'), fdf_annotations.string_to_dict_separator(fdfdsstr, ':',';')]
    

    @staticmethod
    def rgb_inttohex(rgbcolorstring: str) -> str:
        """
        Method that translates the provided rgb colorstring integer values (0-255) to a hexadecimal color string value.
                
        Input: rgbcolorstr: string contaning the 3 int values (0-255) separated by a space. The string may be encapsulated with square brackets.
        Output: hexadecimal string starting with a hashtag followed by the rgb components accordingly (no spacing, 2 hex chars per component)
             E.g. "0 0 255" or "[0 0 255]" --> "#0000FF"  
             In case the provided rgbcolorstr does not meet the expected formatting or is empty, an empty string will be returned.

        """

        if rgbcolorstring=="":
            return ""
        intrgbtag=r"^\[?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*\]?$"      #optional square brackets followed by optional space(s), each rgb component can max consist of 3 digits, separated by at least 1 space.
        intrgbstrmatch=re.search(intrgbtag, rgbcolorstring)
        if intrgbstrmatch:
            return "#" + format(int(intrgbstrmatch.group(1)), "02X") + format(int(intrgbstrmatch.group(2)), "02X") + format(int(intrgbstrmatch.group(3)), "02X")      #zero-padding to 2 digits for each rgb component 

@staticmethod
    def rgb_floattoint(floatcolorstring: str) -> str:
        """
        Method that translates the provided rgb colorstring float values(0.0-1.0) to an integer colorstring separating the rgb components by a space.
                
        Input: rgbcolorstr: string contaning the 3 int values (0-255) separated by a space. The string may be encapsulated with square brackets.
        Output: hexadecimal string starting with a hashtag followed by the rgb components accordingly (no spacing, 2 hex chars per component)
             E.g. "0 0 255" or "[0 0 255]" --> "#0000FF"  
             In case the provided rgbcolorstr does not meet the expected formatting or is empty, an empty string will be returned.

        """

        if rgbcolorstring=="":
            return ""
        intrgbtag=r"^\[?\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*\]?$"      #optional square brackets followed by optional space(s), each rgb component can max consist of 3 digits, separated by at least 1 space.
        intrgbstrmatch=re.search(intrgbtag, rgbcolorstring)
        if intrgbstrmatch:
            return "#" + format(int(intrgbstrmatch.group(1)), "02X") + format(int(intrgbstrmatch.group(2)), "02X") + format(int(intrgbstrmatch.group(3)), "02X")      #zero-padding to 2 digits for each rgb component 
                
        
#additional methods to be added here