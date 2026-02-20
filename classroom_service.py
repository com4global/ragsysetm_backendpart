"""
Classroom / LMS Service — CRUD operations for classrooms, assignments, and progress
"""
import random
import string
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from database import supabase


def _generate_join_code(length: int = 6) -> str:
    """Generate a random uppercase alphanumeric join code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ─── Classrooms ───────────────────────────────────────────────────────────────

def create_classroom(teacher_id: str, name: str, description: str = '', doc_name: str = '') -> Dict:
    """Create a new classroom with a unique join code."""
    join_code = _generate_join_code()
    # Ensure uniqueness (retry up to 5 times)
    for _ in range(5):
        existing = supabase.table('classrooms').select('id').eq('join_code', join_code).execute()
        if not existing.data:
            break
        join_code = _generate_join_code()

    data = {
        'teacher_id': teacher_id,
        'name': name,
        'description': description,
        'doc_name': doc_name,
        'join_code': join_code,
    }
    result = supabase.table('classrooms').insert(data).execute()
    if result.data:
        return result.data[0]
    raise Exception('Failed to create classroom')


def list_classrooms_for_user(user_id: str, role: str = 'student') -> List[Dict]:
    """List classrooms for a user based on their role."""
    if role == 'teacher':
        # Teachers see classrooms they created
        result = supabase.table('classrooms').select('*').eq('teacher_id', user_id).order('created_at', desc=True).execute()
        classrooms = result.data or []
        # Attach student count
        for cls in classrooms:
            members = supabase.table('classroom_members').select('id', count='exact').eq('classroom_id', cls['id']).execute()
            cls['student_count'] = members.count if members.count is not None else len(members.data or [])
        return classrooms
    else:
        # Students see classrooms they joined
        memberships = supabase.table('classroom_members').select('classroom_id').eq('student_id', user_id).execute()
        if not memberships.data:
            return []
        classroom_ids = [m['classroom_id'] for m in memberships.data]
        result = supabase.table('classrooms').select('*').in_('id', classroom_ids).order('created_at', desc=True).execute()
        classrooms = result.data or []
        # Attach teacher name
        for cls in classrooms:
            teacher_profile = supabase.table('profiles').select('full_name').eq('id', cls['teacher_id']).single().execute()
            cls['teacher_name'] = teacher_profile.data.get('full_name', 'Teacher') if teacher_profile.data else 'Teacher'
        return classrooms


def join_classroom(student_id: str, join_code: str) -> Dict:
    """Join a classroom via join code."""
    # Find classroom by code
    result = supabase.table('classrooms').select('*').eq('join_code', join_code.upper()).execute()
    if not result.data:
        raise Exception('Invalid join code')
    classroom = result.data[0]

    # Check if already joined
    existing = supabase.table('classroom_members').select('id') \
        .eq('classroom_id', classroom['id']) \
        .eq('student_id', student_id).execute()
    if existing.data:
        return {'message': 'Already a member', 'classroom': classroom}

    # Join
    supabase.table('classroom_members').insert({
        'classroom_id': classroom['id'],
        'student_id': student_id,
    }).execute()
    return {'message': 'Successfully joined!', 'classroom': classroom}


def get_classroom_detail(classroom_id: str) -> Dict:
    """Get classroom with students and assignments."""
    # Classroom
    cls_result = supabase.table('classrooms').select('*').eq('id', classroom_id).single().execute()
    if not cls_result.data:
        raise Exception('Classroom not found')
    classroom = cls_result.data

    # Students
    members = supabase.table('classroom_members').select('student_id, joined_at') \
        .eq('classroom_id', classroom_id).execute()
    students = []
    for m in (members.data or []):
        profile = supabase.table('profiles').select('id, email, full_name') \
            .eq('id', m['student_id']).single().execute()
        if profile.data:
            students.append({**profile.data, 'joined_at': m['joined_at']})
    classroom['students'] = students

    # Assignments
    assignments = supabase.table('assignments').select('*') \
        .eq('classroom_id', classroom_id).order('created_at', desc=True).execute()
    classroom['assignments'] = assignments.data or []

    return classroom


# ─── Assignments ──────────────────────────────────────────────────────────────

def create_assignment(classroom_id: str, chapter_title: str, topics: List[str] = None, due_date: str = '') -> Dict:
    """Create an assignment for a classroom."""
    data = {
        'classroom_id': classroom_id,
        'chapter_title': chapter_title,
        'topics': json.dumps(topics or []),
        'due_date': due_date if due_date else None,
    }
    result = supabase.table('assignments').insert(data).execute()
    if result.data:
        return result.data[0]
    raise Exception('Failed to create assignment')


# ─── Progress ─────────────────────────────────────────────────────────────────

def update_progress(
    student_id: str,
    topic: str,
    activity_type: str,
    quiz_score: float = 0,
    quiz_answers: Dict = None,
    classroom_id: str = None
) -> Dict:
    """Update progress for a student on a specific topic.
    activity_type: 'conversation' | 'video' | 'quiz'
    """
    # Try to find existing record
    query = supabase.table('student_progress').select('*') \
        .eq('student_id', student_id) \
        .eq('topic', topic)
    if classroom_id:
        query = query.eq('classroom_id', classroom_id)
    else:
        query = query.is_('classroom_id', 'null')

    existing = query.execute()

    if existing.data:
        # Update existing record
        record = existing.data[0]
        updates = {'updated_at': datetime.utcnow().isoformat()}
        if activity_type == 'conversation':
            updates['conversation_completed'] = True
        elif activity_type == 'video':
            updates['video_completed'] = True
        elif activity_type == 'quiz':
            updates['quiz_score'] = quiz_score
            if quiz_answers:
                updates['quiz_answers'] = json.dumps(quiz_answers)

        # Check if all activities are now complete
        conv = updates.get('conversation_completed', record.get('conversation_completed', False))
        vid = updates.get('video_completed', record.get('video_completed', False))
        quiz = updates.get('quiz_score', record.get('quiz_score', 0))
        if conv and vid and quiz > 0:
            updates['completed_at'] = datetime.utcnow().isoformat()

        result = supabase.table('student_progress').update(updates) \
            .eq('id', record['id']).execute()
        return result.data[0] if result.data else record
    else:
        # Create new record
        new_record = {
            'student_id': student_id,
            'classroom_id': classroom_id,
            'topic': topic,
            'conversation_completed': activity_type == 'conversation',
            'video_completed': activity_type == 'video',
            'quiz_score': quiz_score if activity_type == 'quiz' else 0,
            'quiz_answers': json.dumps(quiz_answers or {}),
        }
        result = supabase.table('student_progress').insert(new_record).execute()
        return result.data[0] if result.data else new_record


def get_my_progress(student_id: str, classroom_id: str = None) -> List[Dict]:
    """Get progress for the current student."""
    query = supabase.table('student_progress').select('*').eq('student_id', student_id)
    if classroom_id:
        query = query.eq('classroom_id', classroom_id)
    result = query.execute()
    return result.data or []


def get_classroom_progress(classroom_id: str) -> Dict:
    """Get aggregated progress for all students in a classroom."""
    # Get all members
    members = supabase.table('classroom_members').select('student_id') \
        .eq('classroom_id', classroom_id).execute()
    student_ids = [m['student_id'] for m in (members.data or [])]

    if not student_ids:
        return {'students': [], 'assignments': []}

    # Get assignments for topic list
    assignments = supabase.table('assignments').select('*') \
        .eq('classroom_id', classroom_id).execute()
    all_topics = []
    for a in (assignments.data or []):
        topics = a.get('topics', [])
        if isinstance(topics, str):
            topics = json.loads(topics)
        all_topics.extend(topics)

    # Get progress for each student
    student_summaries = []
    for sid in student_ids:
        profile = supabase.table('profiles').select('id, email, full_name') \
            .eq('id', sid).single().execute()
        progress = supabase.table('student_progress').select('*') \
            .eq('student_id', sid).eq('classroom_id', classroom_id).execute()

        progress_map = {p['topic']: p for p in (progress.data or [])}
        completed_count = sum(1 for t in all_topics if t in progress_map and progress_map[t].get('completed_at'))
        total = len(all_topics) if all_topics else 1

        student_summaries.append({
            'id': sid,
            'email': profile.data.get('email', '') if profile.data else '',
            'full_name': profile.data.get('full_name', '') if profile.data else '',
            'progress_percent': round((completed_count / total) * 100) if total else 0,
            'details': [progress_map.get(t, {}) for t in all_topics],
        })

    return {
        'students': student_summaries,
        'assignments': assignments.data or [],
    }
