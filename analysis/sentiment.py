import spacy
from textblob import TextBlob
import re

# Load spaCy model
nlp = spacy.load('en_core_web_sm')

class ComplaintAnalyzer:
    """Analyzes complaint text to determine category, priority, and sentiment"""
    
    # Category-related keywords
    CATEGORY_KEYWORDS = {
        'MAIN': [
            'broken', 'repair', 'fix', 'maintenance', 'water', 'leak', 'toilet', 'plumbing',
            'electricity', 'power', 'outage', 'air conditioning', 'heating', 'furniture'
        ],
        'SAFE': [
            'safety', 'danger', 'threat', 'unsafe', 'security', 'attack', 'harassment',
            'crime', 'assault', 'theft', 'stolen', 'fight', 'weapon', 'emergency', 'fire'
        ],
        'CLASS': [
            'lecture', 'class', 'professor', 'teacher', 'course', 'curriculum', 'exam',
            'assignment', 'grade', 'classroom', 'schedule', 'syllabus', 'teaching', 'learning'
        ],
        'MISD': [
            'conduct', 'behavior', 'misbehavior', 'misconduct', 'cheat', 'plagiarism',
            'noise', 'loud', 'disturb', 'alcohol', 'drug', 'bullying', 'violation', 'rule'
        ]
    }
    
    # Urgency-related keywords
    URGENCY_KEYWORDS = {
        'CRIT': [
            'urgent', 'immediately', 'emergency', 'critical', 'serious', 'severe',
            'dangerous', 'life-threatening', 'violence', 'assault', 'attack', 'now'
        ],
        'HIGH': [
            'important', 'soon', 'quickly', 'unsafe', 'concerning', 'worried', 'escalate'
        ],
        'MED': [
            'attention', 'issue', 'problem', 'concern', 'address', 'resolve'
        ]
    }
    
    # Staff assignment based on category
    CATEGORY_TO_STAFF = {
        'MAIN': ['WD'],  # Works Department
        'SAFE': ['SEC', 'SA'],  # Security Officer, Student Affairs
        'CLASS': ['SA', 'REG'],  # Student Affairs, Registrar
        'MISD': ['SA', 'HW']  # Student Affairs, Hall Warden
    }
    
    def __init__(self):
        pass
        
    def analyze(self, complaint_text, title=None):
        """
        Analyze the complaint text to determine category, priority, and sentiment
        Returns a dictionary with analysis results
        """
        # Combine title and text for better analysis if title is provided
        full_text = f"{title}. {complaint_text}" if title else complaint_text
        
        # Get sentiment score using TextBlob
        blob = TextBlob(full_text)
        sentiment_score = blob.sentiment.polarity
        
        # Process with spaCy for entity and keyword recognition
        doc = nlp(full_text.lower())
        
        # Determine category based on keyword matching
        category = self._determine_category(doc)
        
        # Determine priority based on keywords and sentiment
        priority = self._determine_priority(doc, sentiment_score)
        
        # Determine which staff roles should be assigned
        assigned_roles = self._determine_staff_assignment(category, priority)
        
        return {
            'category': category,
            'priority': priority,
            'sentiment_score': sentiment_score,
            'assigned_roles': assigned_roles
        }
    
    def _determine_category(self, doc):
        """Determine the complaint category based on keywords"""
        # Count occurrences of keywords for each category
        category_scores = {category: 0 for category in self.CATEGORY_KEYWORDS}
        
        text = doc.text.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    category_scores[category] += 1
        
        # If no clear category is found, default to Misdemeanor Issues
        if max(category_scores.values(), default=0) == 0:
            return 'MISD'
        
        # Return the category with the highest score
        return max(category_scores, key=category_scores.get)
    
    def _determine_priority(self, doc, sentiment_score):
        """Determine priority based on urgency keywords and sentiment"""
        text = doc.text.lower()
        
        # Check for critical urgency keywords first
        for keyword in self.URGENCY_KEYWORDS['CRIT']:
            if keyword.lower() in text:
                return 'CRIT'
        
        # Check for high urgency keywords
        for keyword in self.URGENCY_KEYWORDS['HIGH']:
            if keyword.lower() in text:
                return 'HIGH'
        
        # Check for medium urgency keywords
        for keyword in self.URGENCY_KEYWORDS['MED']:
            if keyword.lower() in text:
                return 'MED'
        
        # If no keywords match, use sentiment score
        # More negative sentiment = higher priority
        if sentiment_score < -0.5:
            return 'HIGH'
        elif sentiment_score < -0.2:
            return 'MED'
        else:
            return 'LOW'
    
    def _determine_staff_assignment(self, category, priority):
        """Determine which staff roles should be assigned to the complaint"""
        assigned_roles = self.CATEGORY_TO_STAFF.get(category, ['SA'])  # Default to Student Affairs
        
        # Critical cases are also assigned to VC and Registrar
        if priority == 'CRIT':
            assigned_roles = list(set(assigned_roles + ['VC', 'REG']))
            
        # High priority cases are assigned to Registrar
        elif priority == 'HIGH':
            assigned_roles = list(set(assigned_roles + ['REG']))
            
        return assigned_roles