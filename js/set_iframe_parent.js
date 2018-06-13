const fs = require('fs')

let content
const path = 'public/login/iframe.html'
fs.readFile(path, 'utf8', function (err, data) {
  if (err) throw err
  content = data.replace(/http:\/\/localhost:3000/g, process.env.ROOT_URL)
  fs.writeFile(path, content, function (err) {
    if (err) throw err
    console.log('iframe.html updated')
  })
})
