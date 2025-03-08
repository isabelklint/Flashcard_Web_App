from flask import Flask, jsonify, render_template

app = Flask(__name__, 
            static_folder='web/static',
            template_folder='web/templates')

@app.route('/')
def home():
    return render_template('dashboard/index.html')

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)

