from base64 import b64decode

class Post:
    
    
    def __init__(self,header:bytes,choix:list,author:str,results={},vote=False,id=0,stats="") -> None:
        """[summary]

        Args:
            header (str): [description]
            choix (list): [description]
        """
        
        self.header = self.unsanitize(header)
        
        self.choix = [self.unsanitize(c) for c in choix] 
        
        self.author = author
        
        self.vote = vote
        
        self.resultats = results
        
        self.id = id
        
        self.stats = stats
        print(stats)
        
        
    def unsanitize(self,header:bytes)->str:
        
        header = b64decode(header).decode("utf-8")
       
        return header