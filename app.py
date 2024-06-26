from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import os, sys, click
from flask import request, url_for, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin
from flask_login import login_user, login_required, logout_user, current_user


# 平台兼容
win = sys.platform.startswith('win')
if win:
    prefix = 'sqlite:///'
else:
    prefix = 'sqlite:////'


#初始化应用、数据库、登陆管理的实例
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '1091'
db = SQLAlchemy(app)


# 定义两个类，用户和电影
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True) # 主键
    name = db.Column(db.String(20)) # 管理员名称
    username = db.Column(db.String(128)) # 用户名
    password_hash = db.Column(db.String(128)) # 密码散列值（哈希）

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def validate_password(self, password):
        return check_password_hash(self.password_hash, password)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True) # 主键
    title = db.Column(db.String(60)) # 电影名称
    year = db.Column(db.String(4)) # 电影年份


# 命令：初始化数据库，可选是否清除数据
@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')


# 命令：导入导入初始数据
@app.cli.command()
def forge():
    db.create_all()

    name = 'NeNoOD'
    movies = [
        {'title': 'My Neighbor Totoro', 'year': '1988'},
        {'title': 'Dead Poets Society', 'year': '1989'},
        {'title': 'A Perfect World', 'year': '1993'},
        {'title': 'Leon', 'year': '1994'},
        {'title': 'Mahjong', 'year': '1996'},
        {'title': 'Swallowtail Butterfly', 'year': '1996'},
        {'title': 'King of Comedy', 'year': '1999'},
        {'title': 'Devils on the Doorstep', 'year': '1999'},
        {'title': 'WALL-E', 'year': '2008'},
        {'title': 'The Pork of Music', 'year': '2012'},
    ]

    for m in movies:
        movie = Movie(title=m['title'], year=m['year'])
        db.session.add(movie)

    db.session.commit()
    click.echo('Done.')


# 命令：创建或者修改管理员账号
@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login')
def admin(username, password):
    db.create_all()

    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password)
    else:
        click.echo('Creating user...')
        user = User(username=username, name="NeNoOD")
        user.set_password(password)
        db.session.add(user)
    
    db.session.commit()
    click.echo('Done.')


# 为html注入user类的上下文环境
@app.context_processor
def inject_user():
    user = User.query.first()
    return dict(user = user)


# 404界面
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# 初始化login扩展
login_manager = LoginManager(app)

@login_manager.user_loader 
def load_user(user_id): # 创建用户加载回调函数，解说用户ID作为参数
    user = User.query.get(int(user_id)) # 用ID作为User模型的主键，查询对应的用户
    return user

login_manager.login_view = 'login'


# 登陆界面
@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 防止恶意的无效请求
        if not username or not password:
            flash('Invalid input')
            return redirect(url_for('index'))
        
        user = User.query.first()
        if username == user.username and user.validate_password(password):
            login_user(user)
            flash('Login success.')
            return redirect(url_for('index'))
        
        flash('Invalid username or password.')
        return redirect(url_for('login'))

    return render_template('login.html')


# 登出界面
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    flash('Goodbye.')
    return redirect(url_for('index'))


# 设置界面
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']

        if not name or len(name) > 20:
            flash('Invalid input.')
            return redirect(url_for('settings'))
        
        current_user.name = name
        db.session.commit()
        flash('Settings updated.')
        return redirect(url_for('settings'))
    
    return render_template('settings.html')



# 主界面，电影列表
@app.route('/', methods = ['GET', 'POST'])
def index():
    # 处理POST请求，添加电影数据
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash("You haven't login!")
            redirect(url_for('index'))

        title = request.form.get('title')
        year = request.form.get('year')

        # 过滤非法输入
        if not title or not year or len(year) > 4 or len(title) > 60:
            flash('Invalid input.')
            return redirect(url_for('index'))
        
        # 将获取到的请求数据加入数据库
        movie = Movie(title = title, year = year)
        db.session.add(movie)
        db.session.commit()
        flash('Item created')
        return redirect(url_for('index'))

    # 获取数据库中所有的电影条目并渲染
    movies = Movie.query.all()
    return render_template('index.html', movies = movies)


# 编辑页面
@app.route('/movie/edit/<int:movie_id>', methods = ['GET', 'POST'])
@login_required
def edit(movie_id):
    movie = Movie.query.get_or_404(movie_id) # 如果没找到主键则返回404

    if request.method == 'POST':
        title = request.form['title']
        year = request.form['year']

        if not title or not year or len(year) != 4 or len(title) > 60:
            flash('Invalid input.')
            return redirect(url_for('edit', movie_id = movie_id))
        
        # 更新电影信息
        movie.title = title
        movie.year = year
        db.session.commit()

        # 更新后显示信息并返回主页面
        flash('Item updated.')
        return redirect(url_for('index'))
    
    return render_template('edit.html', movie = movie)


# 删除页面，限制为仅接受POST请求
@app.route('/movie/delete/<int:movie_id>', methods=["POST"])
@login_required
def delete(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    flash('Item deleted')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)