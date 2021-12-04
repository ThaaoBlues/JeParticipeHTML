class Post:
    
    
    def __init__(self,header:str,choix:list,author:str,vote=False,resultats={},id=0) -> None:
        """[summary]

        Args:
            header (str): [description]
            choix (list): [description]
        """
        self.header = header
        
        self.choix = choix
        
        self.author = author
        
        self.vote = vote
        
        self.resultats = resultats
        
        self.id = id
        
        
    def __sanitize_post(self):
        # make sure no XSS are stored in post
        pass
    
    
    def start_countdown(self):
        """starts a 24h countdown and suppress the post right after
        """
        
        pass