from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from mongoengine import Document, StringField, connect
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import request, render_template, flash, redirect, url_for
from datetime import datetime
from bson import ObjectId

# App config
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

# MongoDB connection using MongoEngine for User and PyMongo for Expenses
connect('Expenses', host='localhost', port=27017)  # MongoEngine for User

# PyMongo setup for expenses collection
client = MongoClient('mongodb://localhost:27017/')
db = client['Expenses']  # Database: Expenses
expenses_collection = db['daily_expense']  # Collection: daily_expense

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -------------------------------
# User Model (MongoEngine)
class User(Document, UserMixin):
    username = StringField(required=True, unique=True)
    password = StringField(required=True)
    preferred_name = StringField(required=True)

    def get_id(self):
        return str(self.id)

# -------------------------------
# Load User (from MongoDB)
@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()

# -------------------------------
# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        preferred_name = request.form['preferred_name']

        # Check if username already exists in MongoEngine (users collection)
        if User.objects(username=username).first():
            flash('Username already exists! Try a different one.')
            return redirect(url_for('register'))

        # Password hashing
        hashed_password = generate_password_hash(password)

        # Save the user to MongoDB using MongoEngine
        User(username=username, password=hashed_password, preferred_name=preferred_name).save()
        flash('Registered successfully. Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')


# -------------------------------
# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.objects(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('all_expenses'))
        flash('Invalid username or password')
        return redirect(url_for('login'))

    return render_template('login.html')


# -------------------------------
@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def all_expenses():
    # Handling the Add Expense Form submission
    if request.method == 'POST':
        # Check if the form data is for adding an expense or deleting an expense
        if 'add_expense' in request.form:
            category = request.form.get('category')
            description = request.form.get('description')
            amount = request.form.get('amount')
            date_str = request.form.get('date')

            # Validate category and description
            valid_categories = expenses_collection.distinct('Category')
            valid_descriptions = expenses_collection.distinct('Description')

            if category not in valid_categories or description not in valid_descriptions:
                flash('Invalid Category or Description selected.', 'danger')
                return redirect(url_for('all_expenses'))

            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                amount_val = float(amount)
            except ValueError:
                flash('Invalid date or amount format.', 'danger')
                return redirect(url_for('all_expenses'))

            # Add the new expense to MongoDB
            new_expense = {
                "user_id": str(current_user.id),
                "Category": category,
                "Description": description,
                "Amount": amount_val,
                "Date": date_obj
            }

            expenses_collection.insert_one(new_expense)
            flash('Expense added successfully!', 'success')

        elif 'delete_expenses' in request.form:
            # Handling the deletion of selected expenses
            expense_ids = request.form.getlist('expense_ids')  # Get the selected expense IDs

            if expense_ids:
                # Delete the selected expenses
                expenses_collection.delete_many({'_id': {'$in': [ObjectId(expense_id) for expense_id in expense_ids]}})
                flash('Selected expenses deleted successfully!', 'danger')
            else:
                flash('No expenses selected for deletion', 'danger')

            return redirect(url_for('all_expenses'))

    # Handle filtering of expenses
    selected_category = request.args.get('category')
    selected_description = request.args.get('description')

    query = {}
    if selected_category:
        query['Category'] = selected_category
    if selected_description:
        query['Description'] = selected_description

    expense_cursor = expenses_collection.find(query)
    expense_list = list(expense_cursor)

    # Safely convert Amount to float
    total_amount = sum(
        float(expense.get('Amount', 0)) 
        for expense in expense_list 
        if expense.get('Amount') not in [None, '']
    )

    total_records = len(expense_list)
    unique_days = len(set(
        expense['Date'].strftime('%Y-%m-%d') 
        for expense in expense_list if expense.get('Date')
    ))

    # Fetch unique values for dropdowns
    categories = expenses_collection.distinct('Category')
    descriptions = expenses_collection.distinct('Description')

    return render_template('expenses.html',
                           expenses=expense_list,
                           total_amount=total_amount,
                           total_records=total_records,
                           unique_days=unique_days,
                           selected_category=selected_category,
                           selected_description=selected_description,
                           categories=categories,
                           descriptions=descriptions)




# -------------------------------
# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
