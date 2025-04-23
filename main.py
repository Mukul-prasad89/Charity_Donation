import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime
import hashlib
import plotly.express as px
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import base64

# --- Database Connection --- #
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ayush@1802",
        database="university_funds"
    )

# --- Hash Password --- #
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Database Setup --- #
def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    pass

# --- User Functions --- #
def add_user(username, password, role='accountant'):
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
        """, (username, password_hash, role))
        conn.commit()
        return True
    except mysql.connector.IntegrityError:
        st.warning("Username already exists.")
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    cursor.execute("""
        SELECT id, username, role FROM users 
        WHERE username=%s AND password_hash=%s
    """, (username, password_hash))
    result = cursor.fetchone()
    conn.close()
    return result

def get_user_role(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# --- Transaction Functions --- #
def insert_income(name, user_id, i_type, description, amount, date, department, status, receipt_path=None):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO income (
                name, user_id, type, description, amount, date, department, status, receipt_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, user_id, i_type, description, amount, date, department, status, receipt_path))

        cursor.execute("UPDATE funds SET balance = balance + %s WHERE id = 1", (amount,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error inserting income: {e}")
        return False
    finally:
        conn.close()

def insert_expense(name, user_id, e_type, description, amount, date, department, status, receipt_path=None):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check current balance first
        cursor.execute("SELECT balance FROM funds WHERE id = 1")
        current_balance = cursor.fetchone()[0]
        
        if float(amount) > float(current_balance):
            st.error(f"Transaction failed: Expense amount (Rs.{amount:,.2f}) exceeds available balance (Rs.{current_balance:,.2f})")
            return False

        cursor.execute("""
            INSERT INTO expenses (
                name, user_id, type, description, amount, date, department, status, receipt_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, user_id, e_type, description, amount, date, department, status, receipt_path))

        cursor.execute("UPDATE funds SET balance = balance - %s WHERE id = 1", (amount,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error inserting expense: {e}")
        return False
    finally:
        conn.close()

def fetch_all_transactions():
    conn = get_connection()
    query = """
        SELECT 
            'income' as transaction_type,
            id, name, user_id, type, description, amount, date, department, status, created_at
        FROM income
        UNION ALL
        SELECT 
            'expense' as transaction_type,
            id, name, user_id, type, description, amount, date, department, status, created_at
        FROM expenses
        ORDER BY date DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def fetch_income():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM income", conn)
    conn.close()
    return df

def fetch_expenses():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM expenses", conn)
    conn.close()
    return df

def get_fund_balance():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM funds WHERE id = 1")
    balance = cursor.fetchone()[0]
    conn.close()
    return balance

# --- Financial Analysis Functions --- #
def get_income_breakdown():
    conn = get_connection()
    query = """
        SELECT 
            type,
            SUM(amount) as total_amount
        FROM income
        GROUP BY type
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_expense_breakdown():
    conn = get_connection()
    query = """
        SELECT 
            type,
            SUM(amount) as total_amount
        FROM expenses
        GROUP BY type
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# --- PDF Generation --- #
def generate_financial_pdf(income_df, expense_df, report_title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    story.append(Paragraph(report_title, styles['Title']))
    story.append(Spacer(1, 12))
    
    # Income Section
    story.append(Paragraph("Income Breakdown", styles['Heading2']))
    if not income_df.empty:
        total_income = income_df['total_amount'].sum()
        story.append(Paragraph(f"Total Income: Rs.{total_income:,.2f}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        for _, row in income_df.iterrows():
            percentage = (row['total_amount'] / total_income) * 100
            story.append(Paragraph(
                f"{row['type']}: Rs.{row['total_amount']:,.2f} ({percentage:.1f}%)", 
                styles['Normal']
            ))
    else:
        story.append(Paragraph("No income data available", styles['Normal']))
    
    story.append(Spacer(1, 24))
    
    # Expense Section
    story.append(Paragraph("Expense Breakdown", styles['Heading2']))
    if not expense_df.empty:
        total_expense = expense_df['total_amount'].sum()
        story.append(Paragraph(f"Total Expenses: Rs.{total_expense:,.2f}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        for _, row in expense_df.iterrows():
            percentage = (row['total_amount'] / total_expense) * 100
            story.append(Paragraph(
                f"{row['type']}: Rs.{row['total_amount']:,.2f} ({percentage:.1f}%)", 
                styles['Normal']
            ))
    else:
        story.append(Paragraph("No expense data available", styles['Normal']))
    
    # Add date and time
    story.append(Spacer(1, 36))
    story.append(Paragraph(
        f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
        styles['Italic']
    ))
    
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# --- Streamlit UI --- #
def main():
    st.set_page_config(page_title="University Funds Management", layout="wide")
    st.title("University Funds Management System")
    st.markdown("### Welcome to Noida Institute of Engineering and Technology")

    initialize_database()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.username = ""
        st.session_state.role = None

    if not st.session_state.logged_in:
        auth_option = st.sidebar.radio("Select", ["Login", "Register"])

        if auth_option == "Register":
            st.subheader("Register New Account")
            with st.form("register_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                role = st.selectbox("Role", ["accountant", "viewer"])
                
                if st.form_submit_button("Register"):
                    if username and password:
                        if add_user(username, password, role):
                            st.success("Registration successful! Please login.")
                    else:
                        st.warning("Username and password are required")

        else:
            st.subheader("User Login")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                if st.form_submit_button("Login"):
                    user = login_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.session_state.role = user[2]
                        st.success(f"Welcome {user[1]} ({user[2]})!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

    if st.session_state.logged_in:
        st.sidebar.write(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
        
        balance = get_fund_balance()
        st.metric("Current Fund Balance", f"Rs.{balance:,.2f}")

        menu = ["Add Income", "Add Expense", "View Transactions", "Generate Report", "Financial Analysis"]
        
        if st.session_state.role == 'viewer':
            menu = ["View Transactions", "Financial Analysis"]
        
        choice = st.sidebar.selectbox("Menu", menu)

        if choice == "Add Income":
            st.subheader("Add New Income")
            with st.form("income_form"):
                name = st.text_input("Full Name")
                i_type = st.selectbox("Income Type", [
                    "Admission Fees", "Government Donation", "Hostel Fees", "Other Income"
                ])
                description = st.text_area("Description")
                amount = st.number_input("Amount (Rs.)", min_value=0.0)
                date = st.date_input("Date", value=datetime.today())
                department = st.selectbox("Department", [
                    "Science", "Arts", "Engineering", "Medicine", "Administration"
                ])
                status = st.selectbox("Status", ["Pending", "Received"])
                
                if st.form_submit_button("Submit"):
                    if name:
                        success = insert_income(
                            name, st.session_state.user_id, i_type, 
                            description, amount, date, department, status
                        )
                        if success:
                            st.success("Income record added successfully!")
                            st.rerun()
                    else:
                        st.warning("Please enter name")

        elif choice == "Add Expense":
            st.subheader("Add New Expense")
            with st.form("expense_form"):
                name = st.text_input("Full Name")
                e_type = st.selectbox("Expense Type", [
                    "Teacher Salary", "Non-Teaching Salary", "Lab Equipment", 
                    "Library Supplies", "Maintenance", "Other Expense"
                ])
                description = st.text_area("Description")
                amount = st.number_input("Amount (Rs.)", min_value=0.0)
                date = st.date_input("Date", value=datetime.today())
                department = st.selectbox("Department", [
                    "Science", "Arts", "Engineering", "Medicine", "Administration"
                ])
                status = st.selectbox("Status", ["Pending", "Paid"])
                
                if st.form_submit_button("Submit"):
                    if name:
                        current_balance = get_fund_balance()
                        st.info(f"Current Available Balance: Rs.{current_balance:,.2f}")
                        
                        if amount > current_balance:
                            st.error("Cannot process expense: Amount exceeds available funds!")
                        else:
                            success = insert_expense(
                                name, st.session_state.user_id, e_type, 
                                description, amount, date, department, status
                            )
                            if success:
                                st.success("Expense record added successfully!")
                                st.rerun()
                    else:
                        st.warning("Please enter name")

        elif choice == "View Transactions":
            st.subheader("All Transactions")
            df = fetch_all_transactions()
            st.dataframe(df)

            with st.expander("Filter Options"):
                col1, col2 = st.columns(2)
                with col1:
                    transaction_type = st.multiselect("Transaction Type", ['income', 'expense'])
                    t_type = st.multiselect("Specific Type", df['type'].unique())
                    department = st.multiselect("Department", df['department'].unique())
                with col2:
                    status = st.multiselect("Status", df['status'].unique())
                    date_range = st.date_input("Date Range", [])

            filtered_df = df
            if transaction_type:
                filtered_df = filtered_df[filtered_df['transaction_type'].isin(transaction_type)]
            if t_type:
                filtered_df = filtered_df[filtered_df['type'].isin(t_type)]
            if status:
                filtered_df = filtered_df[filtered_df['status'].isin(status)]
            if department:
                filtered_df = filtered_df[filtered_df['department'].isin(department)]
            if len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['date'] >= pd.to_datetime(date_range[0])) & 
                    (filtered_df['date'] <= pd.to_datetime(date_range[1]))
                ]

            st.dataframe(filtered_df)
            
            col1, col2 = st.columns(2)
            with col1:
                total_amount = filtered_df['amount'].sum()
                st.metric("Total Amount", f"Rs.{total_amount:,.2f}")
            with col2:
                st.download_button(
                    "Download CSV", 
                    filtered_df.to_csv(index=False), 
                    "transactions_report.csv",
                    "text/csv"
                )

        elif choice == "Financial Analysis":
            st.subheader("Financial Analysis")
            
            income_colors = ['#2ecc71', '#27ae60', '#16a085']
            expense_colors = ['#e74c3c', '#c0392b', '#d35400', '#e67e22', '#f39c12']
            
            with st.container():
                st.markdown("### Income Sources Breakdown")
                income_df = get_income_breakdown()
                
                if not income_df.empty:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        fig_income = px.pie(
                            income_df,
                            values='total_amount',
                            names='type',
                            color_discrete_sequence=income_colors,
                            hole=0.4,
                            title="Income Distribution"
                        )
                        fig_income.update_traces(
                            textposition='inside',
                            textinfo='percent+label+value',
                            hovertemplate="<b>%{label}</b><br>Amount: Rs.%{value:,.2f}<br>%{percent}",
                            pull=[0.1 if i == income_df['total_amount'].idxmax() else 0 for i in range(len(income_df))],
                            marker=dict(line=dict(color='#FFFFFF', width=2))
                        )
                        st.plotly_chart(fig_income, use_container_width=True)
                    
                    with col2:
                        income_df = income_df.rename(columns={
                            'type': 'Source',
                            'total_amount': 'Amount (Rs.)'
                        })
                        income_df['Percentage'] = (income_df['Amount (Rs.)'] / income_df['Amount (Rs.)'].sum() * 100).round(1)
                        st.dataframe(
                            income_df.style.format({
                                'Amount (Rs.)': 'Rs.{:,.2f}',
                                'Percentage': '{:.1f}%'
                            }).background_gradient(cmap='Greens'),
                            height=300,
                            hide_index=True
                        )
                else:
                    st.warning("No income data available")

            st.markdown("---")
            
            with st.container():
                st.markdown("### Expenses Breakdown")
                expense_df = get_expense_breakdown()
                
                if not expense_df.empty:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        fig_expense = px.pie(
                            expense_df,
                            values='total_amount',
                            names='type',
                            color_discrete_sequence=expense_colors,
                            hole=0.4,
                            title="Expense Distribution"
                        )
                        fig_expense.update_traces(
                            textposition='inside',
                            textinfo='percent+label+value',
                            hovertemplate="<b>%{label}</b><br>Amount: Rs.%{value:,.2f}<br>%{percent}",
                            pull=[0.1 if i == expense_df['total_amount'].idxmax() else 0 for i in range(len(expense_df))],
                            marker=dict(line=dict(color='#FFFFFF', width=2))
                        )
                        st.plotly_chart(fig_expense, use_container_width=True)
                    
                    with col2:
                        expense_df = expense_df.rename(columns={
                            'type': 'Category',
                            'total_amount': 'Amount (Rs.)'
                        })
                        expense_df['Percentage'] = (expense_df['Amount (Rs.)'] / expense_df['Amount (Rs.)'].sum() * 100).round(1)
                        st.dataframe(
                            expense_df.style.format({
                                'Amount (Rs.)': 'Rs.{:,.2f}',
                                'Percentage': '{:.1f}%'
                            }).background_gradient(cmap='Reds'),
                            height=300,
                            hide_index=True
                        )
                else:
                    st.warning("No expense data available")
            
            with st.expander("Generate PDF Report"):
                st.write("Create a detailed financial report in PDF format")
                report_title = st.text_input("Report Title", "University Financial Report")
                
                if st.button("Generate PDF Report"):
                    income_data = get_income_breakdown()
                    expense_data = get_expense_breakdown()
                    
                    if not income_data.empty or not expense_data.empty:
                        with st.spinner("Generating PDF report..."):
                            pdf = generate_financial_pdf(income_data, expense_data, report_title)
                            
                            b64 = base64.b64encode(pdf).decode()
                            href = f'<a href="data:application/pdf;base64,{b64}" download="{report_title.replace(" ", "_")}.pdf">Download PDF Report</a>'
                            st.markdown(href, unsafe_allow_html=True)
                            st.success("PDF report generated successfully!")
                    else:
                        st.warning("No financial data available to generate report")

        elif choice == "Generate Report":
            st.subheader("Transaction Summary Report")
            df = fetch_all_transactions()

            with st.expander("Filter Options"):
                col1, col2 = st.columns(2)
                with col1:
                    transaction_type = st.multiselect("Transaction Type", ['income', 'expense'])
                    t_type = st.multiselect("Specific Type", df['type'].unique())
                    department = st.multiselect("Department", df['department'].unique())
                with col2:
                    status = st.multiselect("Status", df['status'].unique())
                    date_range = st.date_input("Date Range", [])

            filtered_df = df
            if transaction_type:
                filtered_df = filtered_df[filtered_df['transaction_type'].isin(transaction_type)]
            if t_type:
                filtered_df = filtered_df[filtered_df['type'].isin(t_type)]
            if status:
                filtered_df = filtered_df[filtered_df['status'].isin(status)]
            if department:
                filtered_df = filtered_df[filtered_df['department'].isin(department)]
            if len(date_range) == 2:
                filtered_df = filtered_df[
                    (filtered_df['date'] >= pd.to_datetime(date_range[0])) & 
                    (filtered_df['date'] <= pd.to_datetime(date_range[1]))
                ]

            st.dataframe(filtered_df)
            
            col1, col2 = st.columns(2)
            with col1:
                total_amount = filtered_df['amount'].sum()
                st.metric("Total Amount", f"Rs.{total_amount:,.2f}")
            with col2:
                st.download_button(
                    "Download CSV", 
                    filtered_df.to_csv(index=False), 
                    "transactions_report.csv",
                    "text/csv"
                )

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = ""
            st.session_state.role = None
            st.rerun()

if __name__ == "__main__":
    main()