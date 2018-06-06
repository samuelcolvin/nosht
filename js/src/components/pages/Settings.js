import React, {Component} from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Row, Col} from 'reactstrap'
import {NotFound} from '../utils/Errors'

const title = s => s.replace(/^\w/, c => c.toUpperCase())
const PAGES = [
  'events',
  'categories',
  'users',
  'company',
  'export',
]

const MenuItem = ({page, location}) => {
  const to = `/settings/${page}/`
  const active = location.pathname === to ? ' active' : ''
  return <Link to={to} className={'list-group-item list-group-item-action' + active}>
    {title(page)}
  </Link>
}

export default class Settings extends Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  render () {
    return (
      <Row>
        <Col md="3">
        <div className="list-group">
          {PAGES.map(p => (
            <MenuItem key={p} page={p} location={this.props.location}/>
          ))}
        </div>
        </Col>
        <Col md="9">
          <Switch>
            <Route exact path="/settings/categories/" render={() => (
              <div>Categories</div>
            )} />

            <Route exact path="/settings/events/" render={() => (
              <div>Events</div>
            )} />

            <Route render={props => (
              <NotFound location={props.location}/>
            )} />
          </Switch>
        </Col>
      </Row>
    )
  }
}
