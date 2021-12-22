from base64 import b64decode

class Post:
    
    
    def __init__(self,header:bytes,choix:list,author:str,author_id:int,results={},vote=False,id=0,stats="") -> None:
        """[summary]

        Args:
            header (str): [description]
            choix (list): [description]
        """
        
        self.header = header
        
        self.choix = choix
        
        self.author_id = author_id
        self.author = author
        
        self.vote = vote
        
        self.resultats = results
        
        self.id = id
        
        self.stats = stats
        
        
    def unsanitize(self,header:bytes)->str:
        
        header = b64decode(header).decode("utf-8")
       
        return header