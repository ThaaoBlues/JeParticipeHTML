class Post:
    
    
    def __init__(self,header:str,choix:list,author:str,results={},vote=False,id=0) -> None:
        """[summary]

        Args:
            header (str): [description]
            choix (list): [description]
        """
        
        self.header = header
        
        self.choix = choix
        
        self.author = author
        
        self.vote = vote
        
        self.resultats = results
        
        self.id = id