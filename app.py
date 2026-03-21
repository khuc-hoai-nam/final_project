from cs50 import SQL
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
# (Đảm bảo dòng này nằm trên cùng, cùng chỗ với mấy dòng import Flask)

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.secret_key = "nam_sport_bi_mat_123" # Đặt một chuỗi bất kỳ

db = SQL("sqlite:///project.db")

@app.route("/")
def index():
    products = db.execute("SELECT * FROM products")
    return render_template("index.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.execute("SELECT * FROM products WHERE id = ?", product_id)
    if not product:
        return "Không tìm thấy sản phẩm", 404
    return render_template("detail.html", product=product[0])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or password != confirmation:
            return "Thông tin không hợp lệ!", 400

        hash_pw = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash, email, phone) VALUES (?, ?, ?, ?)", 
           username, hash_pw, email, phone)
            return render_template("login.html", message="Đăng ký thành công! Vui lòng đăng nhập.")
        except Exception as e:
            # Dòng này sẽ in lỗi thật ra Terminal để bạn soi
            print(f"Lỗi SQL: {e}")
            return f"Lỗi: {e}", 400
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear() # Xóa đăng nhập cũ nếu có
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Tìm user trong DB
        user = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Kiểm tra user và password
        if len(user) != 1 or not check_password_hash(user[0]["hash"], password):
            return "Sai tài khoản hoặc mật khẩu!", 403

        # Lưu vào session
        session["user_id"] = user[0]["id"]
        session["username"] = user[0]["username"]
        return redirect("/")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/cart/add", methods=["POST"])
def cart_add():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    product_id = request.form.get("product_id")
    
    # 1. Lấy thông tin tồn kho của sản phẩm từ DB
    product = db.execute("SELECT stock FROM products WHERE id = ?", product_id)
    
    # 2. Lấy số lượng sản phẩm này đã có sẵn trong giỏ hàng của user
    current_cart = db.execute("SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?", user_id, product_id)
    
    # Số lượng thực tế trong giỏ (nếu chưa có thì là 0)
    qty_in_cart = current_cart[0]["quantity"] if current_cart else 0
    stock_available = product[0]["stock"]

    # 3. KIỂM TRA: Nếu số lượng định mua (đã có + 1) > tồn kho thì chặn lại
    if qty_in_cart + 1 > stock_available:
        # Thay vì hiện lỗi chữ đen, Nam có thể dùng flash message (nếu đã cài) 
        # hoặc tạm thời return thông báo lỗi này
        return f"Lỗi: Kho chỉ còn {stock_available} sản phẩm, bạn không thể thêm nữa!", 400

    # 4. Nếu vượt qua kiểm tra thì mới tiến hành thêm/cập nhật giỏ hàng
    if current_cart:
        db.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?", user_id, product_id)
    else:
        db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)", user_id, product_id)
    
    return redirect("/cart")

@app.route("/cart")
def cart():
    if not session.get("user_id"):
        return redirect("/login")
    
    # THÊM products.id vào câu lệnh SELECT dưới đây
    cart_items = db.execute("""
        SELECT products.id, products.name, products.price, cart.quantity 
        FROM cart 
        JOIN products ON cart.product_id = products.id 
        WHERE cart.user_id = ?
    """, session["user_id"])
    
    total = sum(item["price"] * item["quantity"] for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)

@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    user_id = session.get("user_id")
    product_id = request.form.get("product_id")

    # Lấy thông số hiện tại của món đó
    item = db.execute("SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ?", user_id, product_id)

    if item:
        if item[0]["quantity"] > 1:
            # Nếu còn nhiều hơn 1 -> Giảm đi 1
            db.execute("UPDATE cart SET quantity = quantity - 1 WHERE id = ?", item[0]["id"])
        else:
            # Nếu chỉ còn 1 -> Xóa hẳn dòng đó luôn
            db.execute("DELETE FROM cart WHERE id = ?", item[0]["id"])
            
    return redirect("/cart")

@app.route("/cart/update/<int:product_id>/<action>", methods=["POST"])
def cart_update(product_id, action):
    user_id = session.get("user_id")
    
    if action == "add":
        # Check kho trước khi cho cộng thêm
        product = db.execute("SELECT stock FROM products WHERE id = ?", product_id)
        current_cart = db.execute("SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?", user_id, product_id)
        
        if current_cart[0]["quantity"] + 1 > product[0]["stock"]:
            return "Đã đạt giới hạn tồn kho!", 400
            
        db.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?", user_id, product_id)
    
    # ... (phần code cho action == "remove" giữ nguyên)
    return redirect("/cart")

@app.route("/checkout", methods=["POST"])
def checkout():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    # Tính tổng tiền để hiện lên mã QR
    cart_items = db.execute("""
        SELECT products.price, cart.quantity 
        FROM cart 
        JOIN products ON cart.product_id = products.id 
        WHERE cart.user_id = ?
    """, user_id)
    
    if not cart_items:
        return redirect("/")

    total = sum(item["price"] * item["quantity"] for item in cart_items)
    
    # Truyền số tiền sang trang thanh toán
    return render_template("pay.html", total=total)

@app.route("/payment_confirm", methods=["POST"])
def payment_confirm():
    user_id = session.get("user_id")
    
    # 1. Lấy tất cả món đồ trong giỏ của Nam
    cart_items = db.execute("SELECT product_id, quantity FROM cart WHERE user_id = ?", user_id)
    
    for item in cart_items:
        # 2. Trừ số lượng tồn kho của từng sản phẩm
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", item["quantity"], item["product_id"])
    
    # 3. Xóa sạch giỏ hàng
    db.execute("DELETE FROM cart WHERE user_id = ?", user_id)
    
    return render_template("success.html")

@app.route("/nam")
def products_nam():
    # Giả sử Nam dùng cột 'category' để phân loại
    # Nam có thể sửa 'Nam' thành 'male' tùy theo dữ liệu Nam nhập trong DB
    products = db.execute("SELECT * FROM products WHERE gender = 'Nam' AND stock > 0")
    
    return render_template("nam.html", products=products)

@app.route("/nu")
def products_nu():
    # Giả sử Nam dùng cột 'category' để phân loại
    # Nam có thể sửa 'Nam' thành 'male' tùy theo dữ liệu Nam nhập trong DB
    products = db.execute("SELECT * FROM products WHERE gender = 'Nữ' AND stock > 0")
    
    return render_template("nu.html", products=products)

@app.route("/phu-kien")
def products_phu_kien():
    # Giả sử Nam dùng cột 'category' để phân loại
    # Nam có thể sửa 'Nam' thành 'male' tùy theo dữ liệu Nam nhập trong DB
    products = db.execute("SELECT * FROM products WHERE gender != 'Nữ' AND gender != 'Nam' AND stock > 0")
    
    return render_template("phu-kien.html", products=products)

if __name__ == "__main__":
    app.run(debug=True)