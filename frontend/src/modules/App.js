import React from 'react';
import { BrowserRouter as Router, Route, Link, Switch, NavLink as RRNavLink, useHistory } from 'react-router-dom';
import ReleaseTimeline from './ReleaseTimeline.jsx';
import ReleaseInfo from './ReleaseInfo.jsx';
import InGameTimeline from './InGameTimeline.jsx';
import GameScripts from './GameScripts.jsx';
import { Helmet } from 'react-helmet';
import { RedocStandalone } from 'redoc';
import {
  Collapse,
  Navbar,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink } from 'reactstrap';
import './css/App.css';

const Index = (props) => {
  return (
    <div className="App container">
      <GameScripts setTitleName={props.setTitleName} {...props} />
      <br/>
      <ReleaseInfo />
      <br/>
      <ReleaseTimeline height={750} id="release-timeline"/>
      <br/>
      <InGameTimeline />
    </div>
  );
}

const AppRouter = props => {

  const { listen } = useHistory();

  const [isOpen, setIsOpen] = React.useState(false);
  const [titleName, setTitleName] = React.useState('');

  const toggle = () => {
    setIsOpen(!isOpen);
  }

  React.useEffect(() => {
    return listen((location) => {
      trackPageView();
    });
  }, [listen]);

  const trackPageView = () => {
    if (!window.gtag) {
      return;
    }

    window.gtag('config', 'UA-171690992-1', {page_path: window.location.href});
  }

  return (
    <div>
      <Helmet>
        <title>{titleName}</title>
      </Helmet>
      <Navbar color="light" light expand="md">
        <NavbarBrand tag={RRNavLink} to="/">Trails in the Database</NavbarBrand>
        <NavbarToggler onClick={toggle} />
        <Collapse isOpen={isOpen} navbar>
          <Nav className="mr-auto" navbar>
            <NavItem>
              <NavLink tag={RRNavLink} to="/game-scripts">Game Scripts</NavLink>
            </NavItem>
            <NavItem>
              <NavLink tag={RRNavLink} to="/release-info">Release Info</NavLink>
            </NavItem>
            <NavItem>
              <NavLink tag={RRNavLink} to="/release-timeline">Release Timeline</NavLink>
            </NavItem>
            <NavItem>
              <NavLink tag={RRNavLink} to="/in-game-timeline">In-Game Timeline</NavLink>
            </NavItem>
            <NavItem>
              <NavLink tag={RRNavLink} to="/rest-api-docs">REST API Documentation</NavLink>
            </NavItem>
          </Nav>
        </Collapse>
      </Navbar>
      <Switch>
        <Route path="/" exact render={(props) => <Index setTitleName={setTitleName} {...props} />} />
        <Route path="/release-info" exact component={ReleaseInfo} />
        <Route path="/release-timeline" exact render={() => <ReleaseTimeline height={750} id="release-timeline"/>} />
        <Route path="/in-game-timeline" exact component={InGameTimeline} />
        <Route path="/game-scripts" render={(props) => <GameScripts setTitleName={setTitleName} {...props} />} />
        <Route path="/rest-api-docs" exact>
          <div className="container-fluid">
          <RedocStandalone specUrl="/api/openapi"/>
          </div>
        </Route>
        <Route>
          <div className="container">
            <h2>Not Found</h2>
            <p>That page doesn't exist. <Link to="/">Go home</Link>.</p>
          </div>
        </Route>
      </Switch>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppRouter />
    </Router>
  );
}