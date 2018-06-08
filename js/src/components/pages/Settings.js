import React, {Component} from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Row, Col} from 'reactstrap'
import {NotFound} from '../utils/Errors'
import {EventsList, CategoriesList, UsersList} from './SettingsLists'

const title = s => s.replace(/^\w/, c => c.toUpperCase())
const PAGES = [
  {name: 'events', uri: '/settings/events/', component: EventsList},
  {name: 'categories', uri: '/settings/categories/', component: CategoriesList},
  {name: 'users', uri: '/settings/users/', component: UsersList},
  {name: 'company', uri: '/settings/company/', component: null},
  {name: 'export', uri: '/settings/export/', component: null},
]

const MenuItem = ({page, location}) => {
  const active = location.pathname.startsWith(page.uri) ? ' active' : ''
  return <Link to={page.uri} className={'list-group-item list-group-item-action' + active}>
    {title(page.name)}
  </Link>
}

const MenuPage = ({page, props}) => {
  if (!page.component) {
    return <div>TODO {page.name}</div>
  }
  const MenuComponent = page.component
  return <MenuComponent setRootState={props.setRootState} requests={props.requests}/>
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
            <MenuItem key={p.uri} page={p} location={this.props.location}/>
          ))}
        </div>
        </Col>
        <Col md="9">
          <Switch>
            {PAGES.map(p => (
              <Route key={p.uri} exact path={p.uri} render={() => (
                <MenuPage page={p} props={this.props}/>
              )} />
            ))}

            <Route render={props => (
              <NotFound location={props.location}/>
            )} />
          </Switch>
        </Col>
      </Row>
    )
  }
}
