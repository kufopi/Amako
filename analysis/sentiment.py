# sentiment.py
import spacy
from textblob import TextBlob
import re

nlp = spacy.load('en_core_web_sm')

class ComplaintAnalyzer:
    CATEGORY_KEYWORDS = {
        'INFRA': ['building', 'room', 'lecture hall', 'classroom', 'repair', 'maintenance', 
                 'leak', 'electric', 'power', 'water', 'plumbing', 'furniture', 'facility',
                 'infrastructure', 'broken', 'damaged', 'faulty'],
        'HOSTEL': ['hostel', 'dorm', 'dormitory', 'roommate', 'bathroom', 'common room', 
                  'laundry', 'residence', 'accommodation', 'room allocation'],
        'SAFETY': ['safety', 'danger', 'unsafe', 'threat', 'emergency', 'fire', 'accident',
                  'security', 'theft', 'stolen', 'missing', 'violence'],
        'HARASS': ['harassment', 'bully', 'bullying', 'sexual', 'abuse', 'stalking',
                  'discrimination', 'intimidation', 'unwelcome'],
        'ACAD': ['lecturer', 'professor', 'teacher', 'instructor', 'course', 'class', 'exam', 
                'examination', 'test', 'grade', 'grading', 'assignment', 'marking', 'score', 
                'result', 'department', 'academic', 'curriculum', 'syllabus', 'lecture',
                'tutorial', 'seminar', 'attendance', 'timetable', 'schedule']
    }
    
    PRIORITY_KEYWORDS = {
        'CRIT': ['urgent', 'emergency', 'danger', 'immediately', 'now', 'critical', 
                'asap', 'crisis', 'desperate', 'severe'],
        'HIGH': ['important', 'soon', 'quickly', 'serious', 'concerned', 'worried',
                'significant', 'major', 'pressing', 'vital'],
        'MED': ['problem', 'issue', 'request', 'please', 'kindly', 'help',
               'concern', 'matter', 'situation']
    }
    
    # Time-sensitive patterns for academic complaints
    TIME_PATTERNS = {
        'CRIT': [
            r'\b(tomorrow|today|this week)\b.*\b(exam|test|assessment)\b',
            r'\b(exam|test|assessment)\b.*\b(tomorrow|today|this week)\b',
            r'\b(few days?|couple of days?)\b.*\b(exam|test)\b',
            r'\b(exam|test)\b.*\b(few days?|couple of days?)\b'
        ],
        'HIGH': [
            r'\b(next week|1 week|one week|2 weeks?|two weeks?|3 weeks?|three weeks?)\b.*\b(exam|test|assessment)\b',
            r'\b(exam|test|assessment)\b.*\b(next week|1 week|one week|2 weeks?|two weeks?|3 weeks?|three weeks?)\b',
            r'\bhaven\'?t had.*\b(test|exam|assessment)\b.*\b(weeks?|days?)\b.*\b(exam|test)\b'
        ]
    }
    
    # Academic urgency indicators
    ACADEMIC_URGENCY = {
        'HIGH': ['not coming to class', 'hasn\'t been coming', 'missing lectures', 
                'no test', 'haven\'t had test', 'no assessment', 'weeks to exam',
                'approaching exam', 'exam period', 'final exam'],
        'MED': ['irregular attendance', 'sometimes absent', 'delayed syllabus',
               'behind schedule', 'slow progress']
    }
    
    def analyze(self, text, title=None):
        full_text = f"{title}. {text}" if title else text
        doc = nlp(full_text.lower())
        blob = TextBlob(full_text)
        
        # Determine category
        category_scores = {cat: 0 for cat in self.CATEGORY_KEYWORDS}
        
        # Score based on keyword matches
        for token in doc:
            for cat, keywords in self.CATEGORY_KEYWORDS.items():
                if token.text in keywords:
                    category_scores[cat] += 1
        
        # Check for phrase matches (more accurate for academic complaints)
        full_text_lower = full_text.lower()
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in full_text_lower:
                    category_scores[cat] += 1
        
        category = max(category_scores, key=category_scores.get)
        
        # Determine base priority from keywords
        priority = 'LOW'
        for token in doc:
            for pri, keywords in self.PRIORITY_KEYWORDS.items():
                if token.text in keywords:
                    if pri == 'CRIT':
                        priority = 'CRIT'
                        break
                    elif pri == 'HIGH' and priority != 'CRIT':
                        priority = 'HIGH'
                    elif pri == 'MED' and priority not in ['CRIT', 'HIGH']:
                        priority = 'MED'
        
        # Enhanced priority determination for academic complaints
        if category == 'ACAD':
            priority = self._determine_academic_priority(full_text_lower, priority)
        
        # Adjust priority based on sentiment (more nuanced)
        sentiment = blob.sentiment.polarity
        if sentiment <= -0.4 and priority not in ['CRIT']:
            if category == 'ACAD' and any(phrase in full_text_lower for phrase in ['exam', 'test', 'assessment']):
                priority = 'HIGH'
            elif priority not in ['HIGH']:
                priority = 'HIGH'
        elif sentiment <= -0.15 and priority not in ['CRIT', 'HIGH']:
            priority = 'MED'
        
        return {
            'category': category,
            'priority': priority,
            'sentiment_score': sentiment
        }
    
    def _determine_academic_priority(self, text, current_priority):
        """Enhanced priority determination for academic complaints"""
        
        # Check time-sensitive patterns
        for priority_level, patterns in self.TIME_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if priority_level == 'CRIT':
                        return 'CRIT'
                    elif priority_level == 'HIGH' and current_priority not in ['CRIT']:
                        current_priority = 'HIGH'
        
        # Check academic urgency indicators
        for priority_level, phrases in self.ACADEMIC_URGENCY.items():
            for phrase in phrases:
                if phrase in text:
                    if priority_level == 'HIGH' and current_priority not in ['CRIT']:
                        current_priority = 'HIGH'
                    elif priority_level == 'MED' and current_priority not in ['CRIT', 'HIGH']:
                        current_priority = 'MED'
        
        # Special case: lecturer absence + upcoming exam
        if (any(phrase in text for phrase in ['not coming', 'hasn\'t been coming', 'not been coming']) and 
            any(phrase in text for phrase in ['exam', 'test', 'assessment']) and
            any(phrase in text for phrase in ['weeks', 'days'])):
            if current_priority not in ['CRIT']:
                current_priority = 'HIGH'
        
        return current_priority