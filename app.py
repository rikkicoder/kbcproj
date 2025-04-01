from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import uuid
from flask_mysqldb import MySQL
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure random key

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'         # Change to your MySQL username
app.config['MYSQL_PASSWORD'] = 'Rithvik@2006'  # Change to your MySQL password
app.config['MYSQL_DB'] = 'kbc_game'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'  # Use dictionary cursor for query results

mysql = MySQL(app)

# Global variable to store the accepted user's unique ID
accepted_uid = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/user_login', methods=['POST'])
def user_login():
    name = request.form.get('name')
    email = request.form.get('email')
    dob = request.form.get('dob')
    qualification = request.form.get('qualification')

    if not (name and email and dob and qualification):
        return "Missing fields. Please fill out all required information.", 400

    uid = uuid.uuid4().hex  # Generate a unique user ID

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO users (uid, name, email, dob, qualification, status) VALUES (%s, %s, %s, %s, %s, 'waiting')",
        (uid, name, email, dob, qualification)
    )
    mysql.connection.commit()
    cursor.close()

    # Store the uid in the session (for initial login only)
    session['uid'] = uid
    # Redirect user to their unique waiting URL
    return redirect(url_for('waiting', uid=uid))

@app.route('/admin_login', methods=['POST'])
def admin_login():
    admin_id = request.form.get('admin_id')
    admin_password = request.form.get('admin_password')

    if admin_id == 'admin' and admin_password == 'password':
        session['admin'] = True
        return redirect(url_for('admin_page'))
    else:
        return "Invalid admin credentials", 401

@app.route('/waiting/<uid>')
def waiting(uid):
    # If a user is not logged in or the session uid doesn't match, still allow status check via URL uid.
    return render_template('waiting.html', uid=uid)

@app.route('/admin_page')
def admin_page():
    if not session.get('admin'):
        return redirect(url_for('index'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE status = 'waiting'")
    users = cursor.fetchall()
    cursor.close()

    return render_template('admin_page.html', users=users)

@app.route('/select_user', methods=['POST'])
def select_user():
    if not session.get('admin'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    selected_uid = data.get('selected_uid') if data else None

    if not selected_uid:
        return jsonify({"success": False, "error": "No user selected"}), 400

    global accepted_uid
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE uid = %s", (selected_uid,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"success": False, "error": "User not found"}), 400

    accepted_uid = selected_uid

    # Update the database: mark the selected user as accepted and all others as rejected.
    cursor.execute("UPDATE users SET status = 'accepted' WHERE uid = %s", (selected_uid,))
    cursor.execute("UPDATE users SET status = 'rejected' WHERE uid != %s", (selected_uid,))
    mysql.connection.commit()
    cursor.close()

    # Return JSON success response
    return jsonify({"success": True, "message": "User selected successfully"}), 200




@app.route('/check_game_status/<uid>')
def check_game_status(uid):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT status FROM users WHERE uid = %s", (uid,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        return jsonify({'status': result['status']})
    else:
        return jsonify({'status': 'waiting'})

@app.route('/game/<uid>')
def game(uid):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT status FROM users WHERE uid = %s", (uid,))
    result = cursor.fetchone()
    cursor.close()

    if result and result['status'] == 'accepted':
        # Pass the uid to the game template so it can be used in JS
        return render_template('game.html', uid=uid)
    else:
        return redirect(url_for('not_selected'))

@app.route('/not_selected')
def not_selected():
    return render_template('not_selected.html')

# --- New Endpoints for Game Logic ---

@app.route('/get_questions/<uid>')
def get_questions(uid):
    # Verify the user is accepted
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT status FROM users WHERE uid = %s", (uid,))
    result = cursor.fetchone()
    if not result or result['status'] != 'accepted':
        cursor.close()
        return jsonify({'error': 'User not accepted'}), 403

    questions = []
    # Get 5 random questions per difficulty in order: easy, medium, hard.
    for diff in ['easy', 'medium', 'hard']:
        cursor.execute("SELECT id, question, difficulty, category, correct_answer, incorrect_answers FROM questions WHERE difficulty = %s ORDER BY RAND() LIMIT 5", (diff,))
        questions.extend(cursor.fetchall())
    cursor.close()
    # Return the questions in the order: first 5 (easy), next 5 (medium), last 5 (hard)
    return jsonify({'questions': questions})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    question_id = data.get('question_id')
    selected_answer = data.get('selected_answer')

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT correct_answer FROM questions WHERE id = %s", (question_id,))
    result = cursor.fetchone()
    cursor.close()

    if result:
        # Compare answers ignoring case and extra spaces.
        is_correct = (selected_answer.strip().lower() == result['correct_answer'].strip().lower())
        return jsonify({'correct': is_correct})
    else:
        return jsonify({'error': 'Invalid question id'}), 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/exit_game', methods=['POST'])
def exit_game():
    data = request.get_json()
    reason = data.get('reason', 'voluntary')
    correct_answers = data.get('correct_answers', 0)
    wrong_answer = data.get('wrong_answer', '')
    correct_answer = data.get('correct_answer', '')

    # Earnings table (based on correct answers)
    earnings_table = [
        5000, 10000, 20000, 40000, 80000,
        160000, 320000, 640000, 1250000, 2500000,
        5000000, 10000000, 30000000, 50000000, 70000000
    ]

    # Milestones for guaranteed earnings
    milestone_earnings = {0: 0, 5: 10000, 10: 320000, 15: 70000000}

    # Determine earnings
    if reason == "voluntary":
        earnings = earnings_table[correct_answers - 1] if correct_answers > 0 else 0
    else:  # Player gave a wrong answer
        if correct_answers >= 15:
            earnings = 70000000  # Full win amount
        elif correct_answers >= 10:
            earnings = milestone_earnings[10]  # Guaranteed 3,20,000
        elif correct_answers >= 5:
            earnings = milestone_earnings[5]  # Guaranteed 10,000
        else:
            earnings = milestone_earnings[0]  # No earnings if wrong before milestone 5

    session['game_result'] = {
        'reason': reason,
        'earnings': earnings,
        'correct_answers': correct_answers,
        'wrong_answer': wrong_answer,
        'correct_answer': correct_answer
    }

    return jsonify({'success': True, 'redirect': '/exit'})

@app.route('/exit')
def exit_page():
    game_result = session.get('game_result', {})

    return render_template('exit.html', 
                          reason=game_result.get('reason', 'voluntary'),
                          earnings=game_result.get('earnings', 0),
                          correct_answers=game_result.get('correct_answers', 0),
                          wrong_answer=game_result.get('wrong_answer', ''),
                          correct_answer=game_result.get('correct_answer', ''),
                          is_crorepati=(game_result.get('correct_answers', 0) == 15))


if __name__ == '__main__':
    app.run(debug=True)


# from flask import Flask, render_template, request, redirect, url_for, session, jsonify
# import uuid
# from flask_mysqldb import MySQL
# import json

# app = Flask(__name__)
# app.secret_key = 'your_secret_key_here'  # Replace with a secure random key

# # MySQL Configuration
# app.config['MYSQL_HOST'] = 'localhost'
# app.config['MYSQL_USER'] = 'root'         # Change to your MySQL username
# app.config['MYSQL_PASSWORD'] = 'Rithvik@2006'  # Change to your MySQL password
# app.config['MYSQL_DB'] = 'kbc_game'
# app.config['MYSQL_CURSORCLASS'] = 'DictCursor'  # Use dictionary cursor for query results

# mysql = MySQL(app)

# # Global variable to store the accepted user's unique ID
# accepted_uid = None

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/user_login', methods=['POST'])
# def user_login():
#     name = request.form.get('name')
#     email = request.form.get('email')
#     dob = request.form.get('dob')
#     qualification = request.form.get('qualification')

#     if not (name and email and dob and qualification):
#         return "Missing fields. Please fill out all required information.", 400

#     uid = uuid.uuid4().hex  # Generate a unique user ID

#     cursor = mysql.connection.cursor()
#     cursor.execute(
#         "INSERT INTO users (uid, name, email, dob, qualification, status) VALUES (%s, %s, %s, %s, %s, 'waiting')",
#         (uid, name, email, dob, qualification)
#     )
#     mysql.connection.commit()
#     cursor.close()

#     session['uid'] = uid
#     return redirect(url_for('waiting', uid=uid))

# @app.route('/exit_game', methods=['POST'])
# def exit_game():
#     data = request.get_json()
#     reason = data.get('reason', 'voluntary')
#     correct_answers = data.get('correct_answers', 0)
#     wrong_answer = data.get('wrong_answer', '')
#     correct_answer = data.get('correct_answer', '')
    
#     earnings_table = [
#         5000, 10000, 20000, 40000, 80000,
#         160000, 320000, 640000, 1250000, 2500000,
#         5000000, 10000000, 30000000, 50000000, 70000000
#     ]
    
#     earnings = earnings_table[correct_answers - 1] if 0 < correct_answers <= 15 else 0
    
#     session['game_result'] = {
#         'reason': reason,
#         'earnings': earnings,
#         'correct_answers': correct_answers,
#         'wrong_answer': wrong_answer,
#         'correct_answer': correct_answer,
#         'is_crorepati': correct_answers == 15
#     }
    
#     return jsonify({'success': True, 'redirect': url_for('exit_page')})

# @app.route('/exit')
# def exit_page():
#     game_result = session.get('game_result', {})
#     return render_template('exit.html', **game_result)

# if __name__ == '__main__':
#     app.run(debug=True)
# 