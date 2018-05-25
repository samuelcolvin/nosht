import React, { Component } from 'react'
import Navbar from './components/Navbar'

class App extends Component {
  render () {
    return (
      <div>
        <Navbar/>
        <main className="container">
          <h1 className="mt-5">testing</h1>
          <p className="lead">this is cool.</p>
        </main>
      </div>
    )
  }
}

export default App
